# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The feature-info parsers' failure branches, and the Web Mercator tile maths."""

import pytest

from subphora.geo import box_around, metres_per_pixel, reproject_box, tile_bounds, tile_exists
from subphora.sources.wms import FeatureInfoError, allowed_fields, legend_params, parse_feature_info


@pytest.mark.parametrize(
    ("content", "parser", "message"),
    [
        (b"{not json", "geojson", "not JSON"),
        (b'{"type": "Feature"}', "geojson", "not a GeoJSON FeatureCollection"),
        (b"[1, 2]", "geojson", "not a GeoJSON FeatureCollection"),
        (b'{"features": [{"type": "Feature"}]}', "geojson", "without properties"),
        (b"<FeatureInfoResponse/>", "geojson", "XML where GeoJSON"),
        (b"<html><body>down</body>", "esri_xml", "not XML"),
    ],
)
def test_an_unreadable_answer_is_refused(content: bytes, parser: str, message: str) -> None:
    with pytest.raises(FeatureInfoError, match=message):
        parse_feature_info(content, parser)  # type: ignore[arg-type]


def test_geojson_keeps_plain_values_only() -> None:
    content = b'{"features": [{"properties": {"a": 1, "b": null, "c": {"x": 1}, "d": "t"}}]}'
    assert parse_feature_info(content, "geojson") == [{"a": "1", "d": "t"}]


def test_a_feature_without_any_allowed_field_is_dropped() -> None:
    features = [{"secret": "x"}, {"Name": " River ", "secret": "y"}]
    assert allowed_fields(features, ["Name", "Code"]) == [[("Name", "River")]]


def test_features_that_read_the_same_are_shown_once() -> None:
    # Two polygons of one soil series meet under the tap: their ids differ, nothing shown does.
    features = [
        {"id": "1", "tipus_sol": "Comapregona"},
        {"id": "2", "tipus_sol": "Comapregona"},
        {"id": "3", "tipus_sol": "Morull"},
    ]
    assert allowed_fields(features, ["tipus_sol"]) == [
        [("tipus_sol", "Comapregona")],
        [("tipus_sol", "Morull")],
    ]


def test_a_legend_names_its_style_only_when_there_is_one() -> None:
    assert "STYLE" not in legend_params("a", "")
    assert legend_params("a", "s")["STYLE"] == "s"


def test_the_tile_grid() -> None:
    west, south, east, north = tile_bounds(0, 0, 0)
    assert (west, north) == pytest.approx((-20037508.34, 20037508.34))
    assert (east, south) == pytest.approx((20037508.34, -20037508.34))
    assert tile_bounds(1, 1, 1)[:2] == pytest.approx((0.0, -20037508.34))
    assert metres_per_pixel(0, 256) == pytest.approx(156543.03, rel=1e-6)
    assert not tile_exists(2, 4, 0)
    assert not tile_exists(-1, 0, 0)
    with pytest.raises(ValueError, match="no tile"):
        tile_bounds(2, 0, 4)


def test_a_box_in_another_crs_follows_its_axis_order() -> None:
    box = box_around((-3.7, 40.4), 100)
    south, west, north, east = reproject_box(box, "EPSG:4326")
    assert south < 40.4 < north
    assert west < -3.7 < east
