#!/usr/bin/python
"""Country boundary/bounding-box lookup from HDX's own `cod-ab-global` dataset.

No existing HDX pipeline convention sources country bounding boxes outside OCHA-DAP-internal
blob storage (the pattern used by e.g. hdx-floodscan) -- this module is net-new, verified
against the live HDX API and `cod-ab-global`'s own producer schema (see HDXPIPE-100 analysis,
Stage 2 capability gap / Stage 3.3).
"""

import logging
import zipfile
from pathlib import Path

import geopandas as gpd
from hdx.api.configuration import Configuration
from hdx.utilities.retriever import Retrieve

logger = logging.getLogger(__name__)

ADMIN1_LAYER = "admin1"
ISO3_FIELD = "iso3"


def download_admin1_boundaries(
    retriever: Retrieve, configuration: Configuration, tempdir: str
) -> Path:
    """Download and extract cod-ab-global's admin1 boundaries once per pipeline run.

    HDX's zip has no wrapping `.gdb`-suffixed folder, but GDAL's OpenFileGDB driver requires
    that suffix to recognise a directory as a File Geodatabase, so the extracted contents are
    placed in a manually-named `*.gdb` directory.
    """
    hdx_site_url = configuration.get_hdx_site_url()
    dataset_id = configuration["cod_ab_global_dataset_id"]
    resource_name = configuration["cod_ab_global_resource_name"]

    package = retriever.download_json(
        f"{hdx_site_url}/api/3/action/package_show?id={dataset_id}",
        filename="cod_ab_global_package_show.json",
    )
    resources = package["result"]["resources"]
    resource_url = next(r["url"] for r in resources if r["name"] == resource_name)

    zip_path = retriever.download_file(resource_url, filename=resource_name)

    gdb_dir = Path(tempdir) / "global_admin_boundaries_matched_latest.gdb"
    with zipfile.ZipFile(zip_path) as zip_file:
        zip_file.extractall(gdb_dir)

    return gdb_dir


def get_country_bbox(
    boundaries_path: Path, iso3: str, layer: str | None = ADMIN1_LAYER
) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) for a country from an admin1 boundary layer.

    Accepts any OGR-readable vector source containing a layer with an `iso3` column (the real
    pipeline passes the extracted cod-ab-global GDB and its `admin1` layer; tests pass `layer=None`
    against a small synthetic single-layer fixture, since the full ~1GB GDB is impractical to
    commit).
    """
    gdf = gpd.read_file(boundaries_path, layer=layer)
    country_gdf = gdf[gdf[ISO3_FIELD].str.upper() == iso3.upper()]
    if country_gdf.empty:
        raise ValueError(f"No admin1 boundaries found for country {iso3}")
    minx, miny, maxx, maxy = country_gdf.total_bounds
    return minx, miny, maxx, maxy
