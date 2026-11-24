# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Web Mercator tiles: the EPSG:3857 box of a tile and the size of a pixel at a zoom.

The tile grid is the one MapLibre and the GoogleMapsCompatible matrix set use: at zoom z
the square world is split into 2^z by 2^z tiles, x from the west, y from the north. Its
extent comes from pyproj (longitude 180° in EPSG:3857), not from a written constant.
"""

from functools import cache

from subphora.geo.reproject import to_lon_lat, transform_point

type MercatorBox = tuple[float, float, float, float]

_WEB_MERCATOR = "EPSG:3857"
# Tile grids deeper than this are not drawn by any service in the catalogue.
MAX_TILE_ZOOM = 24


@cache
def _half_extent() -> float:
    return transform_point((180.0, 0.0), _WEB_MERCATOR)[0]


def tile_exists(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_TILE_ZOOM and 0 <= x < 2**z and 0 <= y < 2**z


def tile_bounds(z: int, x: int, y: int) -> MercatorBox:
    """West, south, east, north of tile (z, x, y) in EPSG:3857 metres."""
    if not tile_exists(z, x, y):
        raise ValueError(f"no tile {z}/{x}/{y}")
    half = _half_extent()
    size = 2 * half / 2**z
    west = -half + x * size
    north = half - y * size
    return (west, north - size, west + size, north)


def metres_per_pixel(zoom: float, tile_size: int) -> float:
    """The EPSG:3857 metres one pixel covers at ``zoom`` with tiles of ``tile_size`` px."""
    return 2 * _half_extent() / (tile_size * 2**zoom)


def box_around(point: tuple[float, float], half_width_m: float) -> MercatorBox:
    """The EPSG:3857 square of half-width ``half_width_m`` around a (longitude, latitude)."""
    x, y = transform_point(point, _WEB_MERCATOR)
    return (x - half_width_m, y - half_width_m, x + half_width_m, y + half_width_m)


def reproject_box(box: MercatorBox, crs: str) -> tuple[float, float, float, float]:
    """An EPSG:3857 box as the box enclosing its corners in ``crs``'s own axis order."""
    west, south, east, north = box
    corners = [
        transform_point(p, crs) for p in to_lon_lat([(west, south), (east, north)], _WEB_MERCATOR)
    ]
    firsts = [first for first, _ in corners]
    seconds = [second for _, second in corners]
    return (min(firsts), min(seconds), max(firsts), max(seconds))
