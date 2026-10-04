#!/usr/bin/python
"""
Top level script. Calls other functions that generate datasets that this
script then creates in HDX.

"""

import logging
from os import remove
from os.path import exists, expanduser, join

from hdx.api.configuration import Configuration
from hdx.data.user import User
from hdx.facades.infer_arguments import facade
from hdx.utilities.downloader import Download
from hdx.utilities.path import (
    progress_storing_folder,
    script_dir_plus_file,
    wheretostart_tempdir_batch,
)
from hdx.utilities.retriever import Retrieve

from hdx.scraper.ctrees._version import __version__
from hdx.scraper.ctrees.boundaries import (
    download_admin1_boundaries,
    get_country_bbox,
    get_fieldmaps_country_bbox,
)
from hdx.scraper.ctrees.pipeline import Pipeline

logger = logging.getLogger(__name__)

_LOOKUP = "hdx-scraper-ctrees"
_SAVED_DATA_DIR = "saved_data"  # Keep in repo to avoid deletion in /tmp
_UPDATED_BY_SCRIPT = "HDX Scraper: Ctrees"


def main(
    save: bool = False,
    use_saved: bool = False,
) -> None:
    """Generate datasets and create them in HDX

    Args:
        save: Save downloaded data. Defaults to False.
        use_saved: Use saved data. Defaults to False.

    Returns:
        None
    """
    logger.info(f"##### {_LOOKUP} version {__version__} ####")
    configuration = Configuration.read()
    User.check_current_user_write_access("221a455b-1aca-4f4e-b776-cca7277c4a50")

    with wheretostart_tempdir_batch(folder=_LOOKUP) as info:
        tempdir = info["folder"]
        with Download() as downloader:
            retriever = Retrieve(
                downloader=downloader,
                fallback_dir=tempdir,
                saved_dir=_SAVED_DATA_DIR,
                temp_dir=tempdir,
                save=save,
                use_saved=use_saved,
            )
            pipeline = Pipeline(configuration, retriever, tempdir)
            year = pipeline.find_latest_year()

            countries = [{"iso3": iso3} for iso3 in pipeline.get_gho_countries()]
            boundaries_path = download_admin1_boundaries(
                retriever, configuration, tempdir
            )

            for _, nextdict in progress_storing_folder(info, countries, "iso3"):
                iso3 = nextdict["iso3"]
                tif_path = None
                try:
                    try:
                        bbox = get_country_bbox(boundaries_path, iso3)
                    except ValueError:
                        logger.info(
                            f"{iso3} not in cod-ab-global, using fieldmaps COD boundaries"
                        )
                        bbox = get_fieldmaps_country_bbox(
                            retriever, configuration, iso3
                        )
                    tif_path = pipeline.get_country_raster(iso3, bbox, year)
                    dataset = pipeline.generate_dataset(iso3, tif_path, year)
                    if dataset:
                        dataset.update_from_yaml(
                            script_dir_plus_file(
                                join("config", "hdx_dataset_static.yaml"), main
                            )
                        )
                        dataset.create_in_hdx(
                            remove_additional_resources=True,
                            match_resource_order=False,
                            updated_by_script=_UPDATED_BY_SCRIPT,
                            batch=info["batch"],
                        )
                except Exception:
                    logger.exception(f"Failed to process {iso3}, skipping")
                    continue
                finally:
                    # Outputs reach ~800MB, so delete each before the next is built
                    if tif_path and exists(tif_path):
                        remove(tif_path)


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=join(expanduser("~"), ".useragents.yaml"),
        user_agent_lookup=_LOOKUP,
        project_config_yaml=script_dir_plus_file(
            join("config", "project_configuration.yaml"), main
        ),
    )
