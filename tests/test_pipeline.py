from datetime import UTC, datetime
from os.path import join
from pathlib import Path

import pytest
import rasterio
from hdx.utilities.loader import load_json
from hdx.utilities.path import temp_dir
from hdx.utilities.retriever import Retrieve
from rasterio.errors import RasterioIOError
from rasterio.io import MemoryFile

import hdx.scraper.ctrees.pipeline as pipeline_module
from hdx.scraper.ctrees.pipeline import Pipeline


class TestPipeline:
    def test_get_gho_countries_uses_saved_data_without_network(
        self, monkeypatch, configuration, input_dir
    ):
        def fail_countriesdata(*args, **kwargs):
            raise AssertionError("get_gho_countries should not touch the network")

        monkeypatch.setattr(
            pipeline_module.Country, "countriesdata", fail_countriesdata
        )

        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=True,
        )
        pipeline = Pipeline(configuration, retriever, tempdir=".")
        assert pipeline.get_gho_countries() == ["afg", "lbn"]

    def test_get_gho_countries_saves_fetched_countries(
        self, monkeypatch, configuration
    ):
        countriesdata = {
            "countries": {
                "LBN": {"In GHO": "Y"},
                "AFG": {"In GHO": "Y"},
                "FRA": {"In GHO": None},
            }
        }
        monkeypatch.setattr(
            pipeline_module.Country,
            "countriesdata",
            lambda *args, **kwargs: countriesdata,
        )

        with temp_dir(
            "TestCtreesGHOSave", delete_on_success=True, delete_on_failure=False
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
            assert pipeline.get_gho_countries() == ["afg", "lbn"]
            assert load_json(Path(tempdir) / "gho_countries.json") == {
                "countries": ["afg", "lbn"]
            }

    def _patch_source_cog(self, monkeypatch, input_dir, fill_pixels=()):
        """Stub the /vsicurl/ source COG with the LBN fixture, returning (bbox, data).

        `fill_pixels` are (row, col) positions set to -9999, since the fixture has none.
        """
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
        for row, col in fill_pixels:
            data[row, col] = -9999

        memfile = MemoryFile()
        with memfile.open(**profile) as mem_src:
            mem_src.write(data, 1)

        def fake_open(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith("/vsicurl/"):
                return memfile.open()
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(pipeline_module.rasterio, "open", fake_open)
        return bbox, data

    def test_get_country_raster(self, monkeypatch, configuration, input_dir):
        real_open = rasterio.open
        bbox, _ = self._patch_source_cog(monkeypatch, input_dir)

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
                assert out_src.overviews(1)
                assert (
                    out_src.tags(ns="IMAGE_STRUCTURE")["OVERVIEW_RESAMPLING"].upper()
                    == "AVERAGE"
                )

    def test_get_country_raster_downsampled(
        self, monkeypatch, configuration, input_dir
    ):
        real_open = rasterio.open
        # Top-left 2x2 block: 3 fill pixels, 1 real one. Next block along: all fill.
        fill_pixels = [(0, 1), (1, 0), (1, 1), (0, 2), (0, 3), (1, 2), (1, 3)]
        bbox, src_data = self._patch_source_cog(monkeypatch, input_dir, fill_pixels)
        monkeypatch.setitem(configuration["downsample_factors"], "lbn", 2)

        with temp_dir(
            "TestCtreesRasterDownsampled",
            delete_on_success=True,
            delete_on_failure=False,
        ) as tempdir:
            pipeline = Pipeline(configuration, retriever=None, tempdir=tempdir)
            out_path = pipeline.get_country_raster("lbn", bbox, 2025)

            with real_open(out_path) as out_src:
                data = out_src.read(1)
                assert data.shape == (
                    (src_data.shape[0] + 1) // 2,
                    (src_data.shape[1] + 1) // 2,
                )
                assert out_src.res[0] == pytest.approx(2 * 0.000888888888888)
                assert out_src.nodata == -9999
                # fill pixels are excluded from the average rather than dragging it down
                assert data[0, 0] == src_data[0, 0]
                assert data[0, 1] == -9999
                expected = src_data[2:4, 2:4].mean()
                assert data[1, 1] == pytest.approx(expected, abs=1)

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
        assert dataset["owner_org"] == "221a455b-1aca-4f4e-b776-cca7277c4a50"

        resources = dataset.get_resources()
        assert len(resources) == 1
        assert resources[0]["name"] == "lbn_ctrees_aboveground_biomass.tif"

    def test_generate_dataset_downsampled_description(
        self, monkeypatch, configuration, input_dir
    ):
        monkeypatch.setitem(configuration["downsample_factors"], "lbn", 2)
        tif_path = join(input_dir, "agb_lbn_2025.tif")
        pipeline = Pipeline(configuration, retriever=None, tempdir=input_dir)
        dataset = pipeline.generate_dataset("lbn", tif_path, 2025)
        description = dataset.get_resources()[0]["description"]
        assert "resampled to 200m by averaging" in description

    def test_generate_dataset_unknown_country(self, configuration, input_dir):
        tif_path = join(input_dir, "agb_lbn_2025.tif")
        pipeline = Pipeline(configuration, retriever=None, tempdir=input_dir)
        dataset = pipeline.generate_dataset("zzz", tif_path, 2025)
        assert dataset is None
