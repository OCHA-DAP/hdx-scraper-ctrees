#!/usr/bin/python
"""CTrees scraper"""

import logging
from contextlib import nullcontext
from math import ceil
from os import remove
from os.path import exists, join

import rasterio
import rasterio.shutil
from hdx.api.configuration import Configuration
from hdx.data.dataset import Dataset
from hdx.data.hdxobject import HDXError
from hdx.data.resource import Resource
from hdx.location.country import Country
from hdx.utilities.dateparse import now_utc
from hdx.utilities.loader import load_json
from hdx.utilities.retriever import Retrieve
from hdx.utilities.saver import save_json
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds

logger = logging.getLogger(__name__)

# Jenkins has a 2GB memory limit. Brazil (25,392 columns at 200m) peaks at 395MB with these.
STRIP_ROWS = 1024
GDAL_CACHEMAX_MB = 256


class Pipeline:
    def __init__(self, configuration: Configuration, retriever: Retrieve, tempdir: str):
        self._configuration = configuration
        self._retriever = retriever
        self._tempdir = tempdir

    def get_gho_countries(self) -> list[str]:
        """Fetch the lowercase ISO3 codes of countries in the Global Humanitarian Overview (GHO),
        from the "In GHO" column of hdx-python-country's OCHA countries feed.

        Respects the retriever's save/use_saved flags like every other network call in this
        pipeline: with use_saved, the countries are read back from saved_dir instead of touching
        the network at all; with save, the fetched countries are persisted there for a later
        use_saved run to pick up.
        """
        saved_path = self._retriever.saved_dir / "gho_countries.json"

        if self._retriever.use_saved:
            logger.info(f"Using saved GHO countries in {saved_path}")
            return load_json(saved_path)["countries"]

        countries = sorted(
            iso3.lower()
            for iso3, countryinfo in Country.countriesdata()["countries"].items()
            if countryinfo.get("In GHO") == "Y"
        )
        if self._retriever.save:
            save_json({"countries": countries}, saved_path)
        return countries

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
        countries. The `Scale`/`Offset` GDAL band tags record the conversion back to
        true Mg/ha, but most plain script-based reads (rasterio's `.read()`, GDAL's
        `ReadAsArray()`) do not apply them automatically -- see the resource description/caveats
        for the consumer-facing warning about this.

        The source COG itself carries no GDAL NoData tag (confirmed via `gdalinfo` -- no
        "NoData Value" line), even though its documented fill value is -9999 (from the
        equivalent Zarr source's `_FillValue` attribute, see HDXPIPE-100 analysis 3.3) -- so the
        fill value must come from configuration, not `src.nodata` (which is None here).

        Countries in `downsample_factors` (bra: 2, i.e. 200m) are averaged over factor x factor
        blocks through a WarpedVRT, with the configured fill value excluded from the mean.
        """
        url = self._configuration["agb_cog_url_template"].format(year=year)
        scale_factor = self._configuration["agb_scale_factor"]
        fill_value = self._configuration["agb_fill_value"]
        factor = self._get_downsample_factor(iso3)

        out_path = join(self._tempdir, f"{iso3.lower()}_ctrees_aboveground_biomass.tif")
        tmp_path = join(self._tempdir, f"{iso3.lower()}_strips.tif")
        try:
            with rasterio.Env(GDAL_CACHEMAX=GDAL_CACHEMAX_MB):
                with rasterio.open(f"/vsicurl/{url}") as src:
                    window = from_bounds(*bbox, transform=src.transform)
                    window = window.round_offsets().round_lengths()
                    width = ceil(window.width / factor)
                    height = ceil(window.height / factor)
                    transform = src.window_transform(window) * Affine.scale(factor)
                    if factor == 1:
                        reader = nullcontext(src)
                        offset = (window.col_off, window.row_off)
                    else:
                        reader = WarpedVRT(
                            src,
                            crs=src.crs,
                            transform=transform,
                            width=width,
                            height=height,
                            src_nodata=fill_value,
                            nodata=fill_value,
                            resampling=Resampling.average,
                        )
                        offset = (0, 0)
                    profile = {
                        "width": width,
                        "height": height,
                        "crs": src.crs,
                        "transform": transform,
                        "nodata": fill_value,
                    }
                    with reader as reader_src:
                        self._write_strips(
                            reader_src, offset, tmp_path, profile, scale_factor
                        )
                # COG CreateCopy reads the temp GTiff block by block, so memory stays bounded
                rasterio.shutil.copy(
                    tmp_path,
                    out_path,
                    driver="COG",
                    compress="ZSTD",
                    predictor="STANDARD",
                    level=9,
                    # GDAL's COG default is CUBIC, which overshoots at forest edges (down to
                    # -28.3 Mg/ha in Brazil's overviews)
                    overview_resampling="average",
                    BIGTIFF="IF_SAFER",
                )
        except Exception:
            if exists(out_path):
                remove(out_path)
            raise
        finally:
            if exists(tmp_path):
                remove(tmp_path)

        return out_path

    @staticmethod
    def _write_strips(
        reader, offset: tuple[int, int], tmp_path: str, profile: dict, scale_factor: int
    ) -> None:
        """Copy `reader` to a tiled GTiff STRIP_ROWS rows at a time.

        The COG driver has no Create, so rasterio buffers a COG opened for writing in an
        in-memory dataset -- a full uncompressed copy (1.1GB for Brazil), which with the read
        array exceeded Jenkins' 2GB limit. A GTiff can be written incrementally instead.
        """
        col_off, row_off = offset
        width, height = profile["width"], profile["height"]
        with rasterio.open(
            tmp_path,
            "w",
            driver="GTiff",
            count=1,
            dtype="int16",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="ZSTD",
            zstd_level=1,
            predictor=2,
            BIGTIFF="IF_SAFER",
            **profile,
        ) as dst:
            for row in range(0, height, STRIP_ROWS):
                rows = min(STRIP_ROWS, height - row)
                data = reader.read(
                    1, window=Window(col_off, row_off + row, width, rows)
                )
                dst.write(
                    data.astype("int16", copy=False),
                    1,
                    window=Window(0, row, width, rows),
                )
            dst.scales = (1 / scale_factor,)
            dst.offsets = (0.0,)

    def _get_downsample_factor(self, iso3: str) -> int:
        return self._configuration["downsample_factors"].get(iso3.lower(), 1)

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
        factor = self._get_downsample_factor(iso3)
        if factor == 1:
            resolution = "clipped from CTrees' global 100m-resolution annual raster"
        else:
            resolution = (
                "clipped from CTrees' global 100m-resolution annual raster and resampled "
                f"to {100 * factor}m by averaging"
            )
        resource_name = f"{iso3.lower()}_ctrees_aboveground_biomass.tif"
        resource = Resource(
            {
                "name": resource_name,
                "description": (
                    f"Aboveground biomass for {country_name} in {year}, {resolution}. "
                    "Pixel values are stored as int16, "
                    f"scaled x{scale_factor} relative to true Mg/ha value - see dataset caveats."
                ),
            }
        )
        resource.set_format("geotiff")
        resource.set_file_to_upload(tif_path)
        dataset.add_update_resource(resource)

        return dataset
