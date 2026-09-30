from os.path import join

import pytest
from hdx.utilities.retriever import Retrieve

from hdx.scraper.ctrees.boundaries import get_country_bbox, get_fieldmaps_country_bbox


class TestBoundaries:
    def test_get_country_bbox(self, input_dir):
        boundaries_path = join(input_dir, "admin1.geojson")
        minx, miny, maxx, maxy = get_country_bbox(boundaries_path, "lbn", layer=None)
        assert minx == pytest.approx(35.0)
        assert miny == pytest.approx(33.0)
        assert maxx == pytest.approx(36.7)
        assert maxy == pytest.approx(34.8)

    def test_get_country_bbox_is_case_insensitive(self, input_dir):
        boundaries_path = join(input_dir, "admin1.geojson")
        bbox_lower = get_country_bbox(boundaries_path, "afg", layer=None)
        bbox_upper = get_country_bbox(boundaries_path, "AFG", layer=None)
        assert bbox_lower == bbox_upper

    def test_get_country_bbox_unknown_country(self, input_dir):
        boundaries_path = join(input_dir, "admin1.geojson")
        with pytest.raises(ValueError):
            get_country_bbox(boundaries_path, "zzz", layer=None)

    def test_get_fieldmaps_country_bbox(self, configuration, input_dir):
        retriever = Retrieve(
            downloader=None,
            fallback_dir=input_dir,
            saved_dir=input_dir,
            temp_dir=input_dir,
            save=False,
            use_saved=True,
        )
        minx, miny, maxx, maxy = get_fieldmaps_country_bbox(
            retriever, configuration, "TST"
        )
        assert minx == pytest.approx(10.0)
        assert miny == pytest.approx(20.0)
        assert maxx == pytest.approx(12.0)
        assert maxy == pytest.approx(23.0)
