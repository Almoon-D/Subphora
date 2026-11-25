# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Grids, terrain derivatives, rendering and the nationwide services' answers."""

import io
import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from subphora.geo.grid import (
    GridWindow,
    geometry_bounds,
    lon_lat_bounds,
    transform_geometry,
    transform_xy,
    window_around,
)
from subphora.geo.raster import RasterReadError, burn, distance_to, points_mask, read_geotiff
from subphora.geo.render import colour_png, transparent_png
from subphora.geo.terrain import derive, slope_degrees, wetness_index
from subphora.geo.tiles import tiles_covering
from subphora.sources.national import (
    InputParseError,
    arcgis_query_params,
    check_tiff,
    parse_arcgis_page,
    parse_wfs_page,
    soilgrids_params,
    wcs_params,
    wfs_page_params,
)
from subphora.store.national import TileArchive, write_tiles
from tests.national_support import geotiff

WINDOW = GridWindow(
    crs="EPSG:3035", cell_m=100, west=3_400_000, north=2_100_000, width=40, height=30
)


def test_a_window_is_snapped_outward_to_the_grid() -> None:
    window = window_around("EPSG:3035", 100, (3_400_050, 2_099_950, 3_400_950, 2_100_010))
    assert (window.west, window.north, window.width, window.height) == (3_400_000, 2_100_100, 10, 2)
    assert window.bounds == (3_400_000, 2_099_900, 3_401_000, 2_100_100)
    assert window.cell_of(3_400_050, 2_100_050) == (0, 0)
    assert window.cell_of(3_399_999, 2_100_050) is None
    with pytest.raises(ValueError, match="west, south"):
        window_around("EPSG:3035", 100, (1, 1, 0, 0))


def test_positions_and_geometries_are_reprojected_x_first() -> None:
    x, y = transform_xy(-3.7, 40.4, "EPSG:4326", "EPSG:3035")
    assert 3.1e6 < x < 3.2e6
    assert 1.9e6 < y < 2.1e6
    square = {"type": "Polygon", "coordinates": [[[-3.7, 40.4], [-3.6, 40.4], [-3.6, 40.5]]]}
    moved = transform_geometry(square, "EPSG:4326", "EPSG:3035")
    assert moved["coordinates"][0][0] == pytest.approx([x, y])
    multi = {"type": "MultiPolygon", "coordinates": [square["coordinates"]]}
    assert transform_geometry(multi, "EPSG:4326", "EPSG:3035")["type"] == "MultiPolygon"
    point = transform_geometry(
        {"type": "Point", "coordinates": [-3.7, 40.4]}, "EPSG:4326", "EPSG:3035"
    )
    assert point["coordinates"] == pytest.approx([x, y])
    with pytest.raises(ValueError, match="LineString"):
        transform_geometry({"type": "LineString", "coordinates": []}, "EPSG:4326", "EPSG:3035")
    assert geometry_bounds([square, multi]) == (-3.7, 40.4, -3.6, 40.5)
    with pytest.raises(ValueError, match="no positions"):
        geometry_bounds([{"type": "Polygon", "coordinates": []}])
    west, south, _east, _north = lon_lat_bounds(WINDOW.bounds, WINDOW.crs)
    assert -10 < west < 5
    assert 35 < south < 44


def test_polygons_burn_later_over_earlier_and_distances_are_capped() -> None:
    west, south, east, north = WINDOW.bounds
    whole = {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }
    half = {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [west + 2000, south],
                [west + 2000, north],
                [west, north],
                [west, south],
            ]
        ],
    }
    burnt = burn(WINDOW, [(whole, 1.0), (half, 2.0)], fill=-1.0)
    assert burnt[0, 0] == 2.0
    assert burnt[0, -1] == 1.0
    assert np.all(burn(WINDOW, [], fill=-1.0) == -1.0)
    mask = points_mask(WINDOW, [(west + 50, north - 50), (0.0, 0.0)])
    assert mask.sum() == 1
    distance = distance_to(mask, 100, cap_m=1000)
    assert distance[0, 0] == 0
    assert distance[0, 3] == 300
    assert distance.max() == 1000
    assert np.all(distance_to(np.zeros((2, 2), dtype=bool), 100, 500) == 500)


def test_slope_of_a_plane_and_level_beside_missing_cells() -> None:
    _rows, columns = np.mgrid[0:10, 0:10]
    plane = (columns * 10.0).astype(np.float32)  # 10 m per 100 m cell: 5.71°
    slope = slope_degrees(plane, 100)
    assert slope[5, 5] == pytest.approx(math.degrees(math.atan(0.1)), abs=1e-4)
    flat = np.full((5, 5), 100.0, dtype=np.float32)
    flat[0, :] = np.nan
    assert np.allclose(slope_degrees(flat, 100)[1:], 0.0)
    assert np.all(
        np.isnan(
            wetness_index(
                np.full((1,), np.nan, dtype=np.float32), np.zeros(1, dtype=np.float32), 100, 0.1
            )
        )
    )


def test_terrain_finds_the_valley_floor_as_drainage() -> None:
    rows, columns = np.mgrid[0:40, 0:30]
    valley = (np.abs(columns - 15) * 5.0 + (40 - rows) * 1.0).astype(np.float32)
    window = GridWindow(crs="EPSG:3035", cell_m=100, west=0, north=4000, width=30, height=40)
    terrain = derive(valley, window, channel_area_km2=0.5, min_slope_deg=0.1, distance_cap_m=2000)
    assert terrain.drainage_distance_m[30, 15] == 0
    assert terrain.drainage_distance_m[30, 0] > terrain.drainage_distance_m[30, 12]
    assert terrain.twi[35, 15] > terrain.twi[35, 2]
    assert terrain.upstream_km2[39, 15] > terrain.upstream_km2[5, 15]
    empty = np.full((3, 3), np.nan, dtype=np.float32)
    small = GridWindow(crs="EPSG:3035", cell_m=100, west=0, north=300, width=3, height=3)
    assert np.all(np.isnan(derive(empty, small, 0.5, 0.1, 100).drainage_distance_m))


def test_values_are_coloured_by_class_and_nothing_is_transparent() -> None:
    values = np.array([[0.1, 0.5], [0.9, np.nan]], dtype=np.float32)
    png = colour_png(values, [0.2, 0.8], ["#ff0000", "#00ff00", "#0000ff"])
    assert png is not None
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 0)) == (0, 255, 0, 255)
    assert image.getpixel((0, 1)) == (0, 0, 255, 255)
    assert image.getpixel((1, 1))[3] == 0
    assert (
        colour_png(np.full((2, 2), np.nan, dtype=np.float32), [0.5], ["#000000", "#ffffff"]) is None
    )
    blank = Image.open(io.BytesIO(transparent_png(256))).convert("RGBA")
    assert blank.size == (256, 256)
    assert blank.getpixel((10, 10))[3] == 0


def test_the_tiles_over_a_box() -> None:
    assert tiles_covering((-1.0, 41.0, -0.5, 41.5), 5) == [(15, 11)]
    assert len(tiles_covering((-180, -89, 180, 89), 1)) == 4


def test_a_tile_archive_is_written_read_and_reopened(tmp_path: Path) -> None:
    path = tmp_path / "tiles" / "layer.pmtiles"
    bounds = (-1.0, 41.0, -0.5, 41.5)
    assert write_tiles(path, [], bounds, {}) == 0
    assert not path.exists()
    assert write_tiles(path, [(5, 15, 11, b"one"), (6, 31, 23, b"two")], bounds, {"a": 1}) == 2
    archive = TileArchive(path)
    assert archive.get(5, 15, 11) == b"one"
    assert archive.get(6, 0, 0) is None
    write_tiles(path, [(5, 15, 11, b"new")], bounds, {})
    assert archive.get(5, 15, 11) == b"new"
    path.unlink()
    assert archive.get(5, 15, 11) is None
    archive.close()


# ── The nationwide services' requests and answers ──────────────────────────────────────


def test_requests_carry_the_window_in_the_crs_asked() -> None:
    params = arcgis_query_params((1.0, 2.0, 3.0, 4.0), "EPSG:3035", ["PERME"], 2000, 1000, 25)
    assert params["inSR"] == params["outSR"] == "3035"
    assert params["geometry"] == "1.0,2.0,3.0,4.0"
    assert params["resultOffset"] == "2000"
    assert params["maxAllowableOffset"] == "25"
    assert "maxAllowableOffset" not in arcgis_query_params((0, 0, 1, 1), "EPSG:5635", [], 0, 1)
    with pytest.raises(ValueError, match="EPSG"):
        arcgis_query_params((0, 0, 1, 1), "OGC:CRS84", [], 0, 1)
    wfs = wfs_page_params("agua:x", "EPSG:3857", (1.0, 2.0, 3.0, 4.0), "cod", 50, 50)
    assert wfs["bbox"] == "1.0,2.0,3.0,4.0,EPSG:3857"
    assert wfs["startIndex"] == "50"
    assert wcs_params("Elevacion25830_25", (0, 1, 2, 3))["subset"] == ["x(0.0,2.0)", "y(1.0,3.0)"]
    assert soilgrids_params("clay", (-1, 40, 0, 41))["SUBSET"] == [
        "long(-1.0000,0.0000)",
        "lat(40.0000,41.0000)",
    ]


def test_answers_are_parsed_or_refused() -> None:
    page = parse_arcgis_page(
        json.dumps({"features": [{"a": 1}], "properties": {"exceededTransferLimit": True}}).encode()
    )
    assert page.more
    assert page.features == [{"a": 1}]
    assert not parse_arcgis_page(b'{"features": []}').more
    with pytest.raises(InputParseError) as refused:
        parse_arcgis_page(b'{"error": {"code": 400, "message": "Failed to execute query."}}')
    assert refused.value.transient
    for bad in (b"<html/>", b"not json", b"[]", b'{"features": 3}'):
        with pytest.raises(InputParseError) as error:
            parse_arcgis_page(bad)
        assert not error.value.transient
    assert parse_wfs_page(b'{"features": [{}, {}]}', 2).more
    assert not parse_wfs_page(b'{"features": [{}]}', 2).more
    with pytest.raises(InputParseError):
        parse_wfs_page(b'{"type": "x"}', 2)
    check_tiff(geotiff((0, 0, 100, 100), "EPSG:25830", 25, lambda x, _y: x, "int16"))
    with pytest.raises(InputParseError, match="ExtentError"):
        check_tiff(b"<ows:ExceptionReport>ExtentError</ows:ExceptionReport>")


def test_a_geotiff_is_read_with_its_georeference() -> None:
    content = geotiff((0, 0, 100, 50), "EPSG:25830", 25, lambda x, _y: x, "int16")
    raster = read_geotiff(content)
    assert raster.data.shape == (2, 4)
    assert raster.crs == "EPSG:25830"
    assert raster.transform.c == 0
    assert raster.transform.f == 50
    with pytest.raises(RasterReadError):
        read_geotiff(b"II*\x00garbage")
