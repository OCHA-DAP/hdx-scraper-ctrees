#!/usr/bin/python
"""CTrees scraper"""

import logging
from os.path import join

import rasterio
from hdx.api.configuration import Configuration
from hdx.data.dataset import Dataset
from hdx.data.hdxobject import HDXError
from hdx.data.resource import Resource
from hdx.location.country import Country
from hdx.utilities.dateparse import now_utc
from hdx.utilities.loader import load_json
from hdx.utilities.retriever import Retrieve
from hdx.utilities.saver import save_json
from rasterio.errors import RasterioIOError
from rasterio.windows import from_bounds

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, configuration: Configuration, retriever: Retrieve, tempdir: str):
        self._configuration = configuration
        self._retriever = retriever
        self._tempdir = tempdir

    def get_data_grid_countries(self) -> list[str]:
        """Fetch HDX's active Data Grid countries (3-letter group names).

        Treated as a live/short-TTL lookup rather than a frozen static list, since Data Grid
        membership changes over time.
        """
        hdx_site_url = self._configuration.get_hdx_site_url()
        response = self._retriever.download_json(
            f"{hdx_site_url}/api/3/action/group_list?all_fields=true&include_extras=true",
            filename="data_grid_group_list.json",
        )
        groups = response["result"]
        return sorted(
            group["name"]
            for group in groups
            if len(group["name"]) == 3 and group.get("data_completeness") == "active"
        )

    def find_latest_year(self) -> int:
        """Find the latest year for which the source AGB COG is published.

        Starts at the current UTC year and walks backwards (the source is typically a year or
        more behind real-time), opening each year's COG via /vsicurl/ until one succeeds --
        reusing the same open call as get_country_raster, since a COG open here only reads
        header/metadata, not the full ~38GB file.

        Respects the retriever's save/use_saved flags like every other network call in this
        pipeline: with use_saved, the year is read back from saved_dir instead of touching the
        network at all; with save, the discovered year is persisted there for a later use_saved
        run to pick up.
        """
        saved_path = self._retriever.saved_dir / "latest_year.json"

        if self._retriever.use_saved:
            logger.info(f"Using saved latest year in {saved_path}")
            return load_json(saved_path)["year"]

        url_template = self._configuration["agb_cog_url_template"]
        max_lookback = self._configuration["max_year_lookback"]
        current_year = now_utc().year

        for year in range(current_year, current_year - max_lookback - 1, -1):
            url = url_template.format(year=year)
            try:
                with rasterio.open(f"/vsicurl/{url}"):
                    if self._retriever.save:
                        save_json({"year": year}, saved_path)
                    return year
            except RasterioIOError:
                continue

        raise RasterioIOError(
            f"No AGB COG found for years {current_year} down to {current_year - max_lookback}"
        )

    def get_country_raster(
        self, iso3: str, bbox: tuple[float, float, float, float], year: int
    ) -> str:
        """Clip the global AGB COG for `year` to `bbox` and write a per-country COG.

        Reads a windowed slice of the public S3 COG mirror via GDAL's /vsicurl/ streaming
        (only the byte ranges intersecting the window are fetched, never the whole ~38GB file).

        Written as the source's native int16 (still scaled x`agb_scale_factor`, not divided) --
        per HDXPIPE-100 analysis 5.5/5.6, this halves the file size vs. float32 for the largest
        Data Grid countries. The `Scale`/`Offset` GDAL band tags record the conversion back to
        true Mg/ha, but most plain script-based reads (rasterio's `.read()`, GDAL's
        `ReadAsArray()`) do not apply them automatically -- see the resource description/caveats
        for the consumer-facing warning about this.

        The source COG itself carries no GDAL NoData tag (confirmed via `gdalinfo` -- no
        "NoData Value" line), even though its documented fill value is -9999 (from the
        equivalent Zarr source's `_FillValue` attribute, see HDXPIPE-100 analysis 3.3) -- so the
        fill value must come from configuration, not `src.nodata` (which is None here).
        """
        url = self._configuration["agb_cog_url_template"].format(year=year)
        scale_factor = self._configuration["agb_scale_factor"]
        fill_value = self._configuration["agb_fill_value"]

        with rasterio.open(f"/vsicurl/{url}") as src:
            window = from_bounds(*bbox, transform=src.transform)
            window = window.round_offsets().round_lengths()
            data = src.read(1, window=window)
            transform = src.window_transform(window)
            crs = src.crs

        data = data.astype("int16")

        profile = {
            "driver": "COG",
            "height": data.shape[0],
            "width": data.shape[1],
            "count": 1,
            "dtype": "int16",
            "crs": crs,
            "transform": transform,
            "nodata": fill_value,
            "compress": "ZSTD",
            "predictor": "STANDARD",
            "level": 9,
        }

        out_path = join(self._tempdir, f"{iso3.lower()}_ctrees_aboveground_biomass.tif")
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data, 1)
            dst.scales = (1 / scale_factor,)
            dst.offsets = (0.0,)

        return out_path

    def generate_dataset(self, iso3: str, tif_path: str, year: int) -> Dataset | None:
        country_name = Country.get_country_name_from_iso3(iso3)
        if country_name is None:
            logger.error(f"Unknown country {iso3}, skipping")
            return None

        dataset_name = f"{iso3.lower()}-ctrees-aboveground-biomass"
        dataset_title = (
            f"{country_name} - {self._configuration['dataset_title_suffix']}"
        )

        dataset = Dataset(
            {
                "name": dataset_name,
                "title": dataset_title,
            }
        )
        dataset.set_time_period_year_range(year)
        dataset.add_tags(self._configuration["tags"])
        dataset.set_subnational(True)
        try:
            dataset.add_country_location(iso3)
        except HDXError:
            logger.error(f"Couldn't find country {iso3}, skipping")
            return None

        scale_factor = self._configuration["agb_scale_factor"]
        resource_name = f"{iso3.lower()}_ctrees_aboveground_biomass.tif"
        resource = Resource(
            {
                "name": resource_name,
                "description": (
                    f"Aboveground biomass for {country_name} in {year}, clipped from CTrees' "
                    "global 100m-resolution annual raster. Pixel values are stored as int16, "
                    f"scaled x{scale_factor} relative to true Mg/ha value - see dataset caveats."
                ),
            }
        )
        resource.set_format("geotiff")
        resource.set_file_to_upload(tif_path)
        dataset.add_update_resource(resource)

        return dataset
