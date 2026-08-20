from datetime import UTC, datetime
from os.path import join
from pathlib import Path

import pytest
import rasterio
from hdx.utilities.downloader import Download
from hdx.utilities.loader import load_json
from hdx.utilities.path import temp_dir
from hdx.utilities.retriever import Retrieve
from rasterio.errors import RasterioIOError
from rasterio.io import MemoryFile

import hdx.scraper.ctrees.pipeline as pipeline_module
from hdx.scraper.ctrees.pipeline import Pipeline


class TestPipeline:
    def test_get_data_grid_countries(self, configuration, input_dir):
        with temp_dir(
            "TestCtreesDataGrid", delete_on_success=True, delete_on_failure=False
        ) as tempdir:
            with Download(user_agent="test") as downloader:
                retriever = Retrieve(
                    downloader=downloader,
                    fallback_dir=tempdir,
                    saved_dir=input_dir,
                    temp_dir=tempdir,
                    save=False,
                    use_saved=True,
                )
                pipeline = Pipeline(configuration, retriever, tempdir)
                countries = pipeline.get_data_grid_countries()

        # excludes "syr" (inactive) and "world" (not a 3-letter country group)
        assert countries == ["afg", "lbn"]

    def test_get_country_raster(self, monkeypatch, configuration, input_dir):
        fixture_path = join(input_dir, "agb_lbn_2025.tif")
        real_open = rasterio.open

        # The real S3 COG carries no GDAL NoData tag at all (confirmed via gdalinfo), unlike
        # this fixture (captured via rioxarray, which does set one) -- strip it here so the
        # mock matches the real source. Without this, a regression to reading src.nodata
        # instead of the configured agb_fill_value would pass against the fixture but silently
        # leak -9999 sentinel values through against the real source (see HDXPIPE-100 analysis).
        with real_open(fixture_path) as fixture_src:
            data = fixture_src.read(1)
            profile = fixture_src.profile.copy()
            bbox = tuple(fixture_src.bounds)
        profile["nodata"] = None

        memfile = MemoryFile()
        with memfile.open(**profile) as mem_src:
            mem_src.write(data, 1)

        def fake_open(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith("/vsicurl/"):
                return memfile.open()
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(pipeline_module.rasterio, "open", fake_open)

        with temp_dir(
            "TestCtreesRaster", delete_on_success=True, delete_on_failure=False
        ) as tempdir:
            pipeline = Pipeline(configuration, retriever=None, tempdir=tempdir)
            out_path = pipeline.get_country_raster("lbn", bbox, 2025)

            with real_open(out_path) as out_src:
                data = out_src.read(1)
                assert data.shape[0] > 0
                assert data.shape[1] > 0
                assert out_src.dtypes[0] == "int16"
                # raw fixture range is 0-3870 (already x10-scaled, stored undivided)
                assert data.max() == pytest.approx(3870, rel=0.01)
                assert data.min() == 0
                # fill value is tagged as nodata (rather than divided/converted to nan), so
                # readers that respect the nodata tag mask it correctly
                assert out_src.nodata == -9999
                # scale/offset band tags record how to recover true Mg/ha (raw / 10)
                assert out_src.scales[0] == pytest.approx(0.1)
                assert out_src.offsets[0] == pytest.approx(0.0)

    def _patch_now_utc(self, monkeypatch, year):
        monkeypatch.setattr(
            pipeline_module,
            "now_utc",
            lambda: datetime(year, 8, 7, tzinfo=UTC),
        )

    def _patch_available_years(self, monkeypatch, available_years):
        class _DummyDataset:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_open(path, *args, **kwargs):
            if any(f"_{year}_" in path for year in available_years):
                return _DummyDataset()
            raise RasterioIOError("HTTP response code: 404")

        monkeypatch.setattr(pipeline_module.rasterio, "open", fake_open)

    def test_find_latest_year_current_year_available(
        self, monkeypatch, configuration, input_dir
    ):
        self._patch_now_utc(monkeypatch, 2025)
        self._patch_available_years(monkeypatch, {2025, 2024})

        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=False,
        )
        pipeline = Pipeline(configuration, retriever, tempdir=".")
        assert pipeline.find_latest_year() == 2025

    def test_find_latest_year_falls_back_to_previous_year(
        self, monkeypatch, configuration, input_dir
    ):
        # current year (2026) not yet published, as is the case for the real source today
        self._patch_now_utc(monkeypatch, 2026)
        self._patch_available_years(monkeypatch, {2025, 2024})

        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=False,
        )
        pipeline = Pipeline(configuration, retriever, tempdir=".")
        assert pipeline.find_latest_year() == 2025

    def test_find_latest_year_raises_when_none_found(
        self, monkeypatch, configuration, input_dir
    ):
        self._patch_now_utc(monkeypatch, 2026)
        self._patch_available_years(monkeypatch, set())

        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=False,
        )
        pipeline = Pipeline(configuration, retriever, tempdir=".")
        with pytest.raises(RasterioIOError):
            pipeline.find_latest_year()

    def test_find_latest_year_uses_saved_data_without_network(
        self, monkeypatch, configuration, input_dir
    ):
        def fake_open(path, *args, **kwargs):
            raise AssertionError("find_latest_year should not touch the network")

        monkeypatch.setattr(pipeline_module.rasterio, "open", fake_open)

        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=True,
        )
        pipeline = Pipeline(configuration, retriever, tempdir=".")
        assert pipeline.find_latest_year() == 2025

    def test_find_latest_year_saves_discovered_year(self, monkeypatch, configuration):
        self._patch_now_utc(monkeypatch, 2025)
        self._patch_available_years(monkeypatch, {2025, 2024})

        with temp_dir(
            "TestCtreesLatestYearSave", delete_on_success=True, delete_on_failure=False
        ) as tempdir:
            retriever = Retrieve(
                downloader=None,
                fallback_dir=tempdir,
                saved_dir=tempdir,
                temp_dir=tempdir,
                save=True,
                use_saved=False,
            )
            pipeline = Pipeline(configuration, retriever, tempdir=".")
            assert pipeline.find_latest_year() == 2025
            assert load_json(Path(tempdir) / "latest_year.json") == {"year": 2025}

    def test_generate_dataset(self, configuration, input_dir, config_dir):
        tif_path = join(input_dir, "agb_lbn_2025.tif")
        pipeline = Pipeline(configuration, retriever=None, tempdir=input_dir)
        dataset = pipeline.generate_dataset("lbn", tif_path, 2025)

        assert dataset["name"] == "lbn-ctrees-aboveground-biomass"
        assert dataset["title"] == "Lebanon - Aboveground Biomass"

        dataset.update_from_yaml(path=join(config_dir, "hdx_dataset_static.yaml"))
        assert dataset["owner_org"] == "22b445e2-97ee-436d-994a-4a4c8c63c847"

        resources = dataset.get_resources()
        assert len(resources) == 1
        assert resources[0]["name"] == "lbn_ctrees_aboveground_biomass.tif"

    def test_generate_dataset_unknown_country(self, configuration, input_dir):
        tif_path = join(input_dir, "agb_lbn_2025.tif")
        pipeline = Pipeline(configuration, retriever=None, tempdir=input_dir)
        dataset = pipeline.generate_dataset("zzz", tif_path, 2025)
        assert dataset is None
