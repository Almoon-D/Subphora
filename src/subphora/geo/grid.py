# Copyright (c) 2026 Almoon-D. All rights reserved.
"""National grids: square cells of a fixed size in a projected CRS, aligned to multiples of
the cell size from the CRS origin, so every window of one grid shares its cells.

Coordinates here are always (x, y) = (easting, northing), the order GeoTIFF and the raster
library use, whatever axis order the CRS defines; pyproj transforms them with
``always_xy``.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from affine import Affine
from pyproj import Transformer

type Bounds = tuple[float, float, float, float]

_LON_LAT = "EPSG:4326"
# Points along each side of a box when its bounds are reprojected, so curved sides count.
_DENSIFY = 21


@lru_cache(maxsize=32)
def _transformer(source: str, target: str) -> Transformer:
    return Transformer.from_crs(source, target, always_xy=True)


def transform_xy(x: float, y: float, source: str, target: str) -> tuple[float, float]:
    """A position (x first, whatever the CRSs' axis order) from ``source`` to ``target``."""
    out_x, out_y = _transformer(source, target).transform(x, y, errcheck=True)
    return float(out_x), float(out_y)


def transform_bounds(bounds: Bounds, source: str, target: str) -> Bounds:
    """The box in ``target`` that encloses ``bounds`` (x first in both)."""
    west, south, east, north = _transformer(source, target).transform_bounds(
        *bounds, densify_pts=_DENSIFY, errcheck=True
    )
    return (float(west), float(south), float(east), float(north))


def lon_lat_bounds(bounds: Bounds, crs: str) -> Bounds:
    return transform_bounds(bounds, crs, _LON_LAT)


@dataclass(frozen=True, slots=True)
class GridWindow:
    """A window of a national grid: its CRS, cell size, north-west corner and size."""

    crs: str
    cell_m: float
    west: float
    north: float
    width: int
    height: int

    @property
    def transform(self) -> Affine:
        return Affine(self.cell_m, 0.0, self.west, 0.0, -self.cell_m, self.north)

    @property
    def bounds(self) -> Bounds:
        return (
            self.west,
            self.north - self.height * self.cell_m,
            self.west + self.width * self.cell_m,
            self.north,
        )

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    def cell_of(self, x: float, y: float) -> tuple[int, int] | None:
        """The (row, column) holding a position in the grid's CRS, or None outside."""
        column = math.floor((x - self.west) / self.cell_m)
        row = math.floor((self.north - y) / self.cell_m)
        if 0 <= row < self.height and 0 <= column < self.width:
            return (row, column)
        return None


def window_around(crs: str, cell_m: float, bounds: Bounds) -> GridWindow:
    """The smallest window of the grid that covers ``bounds`` (in the grid's CRS)."""
    west, south, east, north = bounds
    if not (west < east and south < north):
        raise ValueError("bounds must be west, south, east, north")
    snapped_west = math.floor(west / cell_m) * cell_m
    snapped_east = math.ceil(east / cell_m) * cell_m
    snapped_south = math.floor(south / cell_m) * cell_m
    snapped_north = math.ceil(north / cell_m) * cell_m
    return GridWindow(
        crs=crs,
        cell_m=cell_m,
        west=snapped_west,
        north=snapped_north,
        width=round((snapped_east - snapped_west) / cell_m),
        height=round((snapped_north - snapped_south) / cell_m),
    )


def buffered(bounds: Bounds, distance: float) -> Bounds:
    west, south, east, north = bounds
    return (west - distance, south - distance, east + distance, north + distance)


def transform_geometry(geometry: dict[str, Any], source: str, target: str) -> dict[str, Any]:
    """A GeoJSON Point, Polygon or MultiPolygon (x first) from ``source`` to ``target``."""
    transformer = _transformer(source, target)

    def ring(points: list[list[float]]) -> list[list[float]]:
        if not points:
            return []
        xs, ys = zip(*((p[0], p[1]) for p in points), strict=True)
        out_x, out_y = transformer.transform(xs, ys, errcheck=True)
        return [[float(x), float(y)] for x, y in zip(out_x, out_y, strict=True)]

    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Point" and isinstance(coordinates, list):
        return {"type": kind, "coordinates": ring([coordinates])[0]}
    if kind == "Polygon" and isinstance(coordinates, list):
        return {"type": kind, "coordinates": [ring(r) for r in coordinates]}
    if kind == "MultiPolygon" and isinstance(coordinates, list):
        return {"type": kind, "coordinates": [[ring(r) for r in p] for p in coordinates]}
    raise ValueError(f"cannot transform a {kind} geometry")


def geometry_bounds(geometries: list[dict[str, Any]]) -> Bounds:
    """West, south, east, north of every position of GeoJSON polygons and multipolygons."""
    xs: list[float] = []
    ys: list[float] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and all(isinstance(v, int | float) for v in value[:2])
        ):
            xs.append(float(value[0]))
            ys.append(float(value[1]))
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for geometry in geometries:
        walk(geometry.get("coordinates"))
    if not xs:
        raise ValueError("no positions to bound")
    return (min(xs), min(ys), max(xs), max(ys))
