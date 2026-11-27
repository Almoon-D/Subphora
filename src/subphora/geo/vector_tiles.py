# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Polygons out of a Mapbox vector tile (MVT/PBF), as GeoJSON in EPSG:3857.

GDAL's MVT driver (through pyogrio) decodes the tile, told its z/x/y so that coordinates
come out in Web Mercator; its WKB geometries are turned into GeoJSON here, since burning
them into a grid takes GeoJSON mappings.
"""

import struct
from typing import Any

import numpy as np
import pyogrio.raw

from subphora.geo.raster import Geometry

_POLYGON = 3
_MULTIPOLYGON = 6
_LITTLE_ENDIAN = 1
# The geometry types with an area, and an unreadable header (refused by wkb_polygon).
_AREAS = {_POLYGON, _MULTIPOLYGON, None}


class VectorTileError(ValueError):
    """Bytes that are not a readable vector tile, or a geometry this reader does not know."""


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._at = 0
        self._order = "<"

    def byte_order(self) -> None:
        self._order = "<" if self._data[self._at] == _LITTLE_ENDIAN else ">"
        self._at += 1

    def uint(self) -> int:
        (value,) = struct.unpack_from(self._order + "I", self._data, self._at)
        self._at += 4
        return int(value)

    def points(self, count: int) -> list[list[float]]:
        values = struct.unpack_from(f"{self._order}{2 * count}d", self._data, self._at)
        self._at += 16 * count
        return [[values[i], values[i + 1]] for i in range(0, 2 * count, 2)]

    def polygon_rings(self) -> list[list[list[float]]]:
        return [self.points(self.uint()) for _ in range(self.uint())]

    def header(self) -> int:
        self.byte_order()
        return self.uint()


def wkb_polygon(data: bytes) -> Geometry:
    """A 2D Polygon or MultiPolygon WKB as GeoJSON; raises VectorTileError otherwise."""
    reader = _Reader(data)
    try:
        kind = reader.header()
        if kind == _POLYGON:
            return {"type": "Polygon", "coordinates": reader.polygon_rings()}
        if kind == _MULTIPOLYGON:
            polygons = []
            for _ in range(reader.uint()):
                if reader.header() != _POLYGON:
                    raise VectorTileError("a multipolygon holds a non-polygon")
                polygons.append(reader.polygon_rings())
            return {"type": "MultiPolygon", "coordinates": polygons}
    except (struct.error, IndexError) as exc:
        raise VectorTileError(f"truncated geometry: {exc}") from exc
    raise VectorTileError(f"geometry type {kind} is not a 2D polygon")


def _number(value: Any) -> float | None:
    """A tile attribute as a number: GDAL types a field by what the tile holds."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return None if np.isnan(number) else number


def polygons_at_least(
    content: bytes, tile: tuple[int, int, int], layer: str, field: str, minimum: float
) -> list[Geometry]:
    """The polygons of ``layer`` whose numeric ``field`` is at least ``minimum``, in
    EPSG:3857; an empty tile (no bytes) has none. Raises VectorTileError."""
    if not content:
        return []
    z, x, y = tile
    try:
        layers = {str(row[0]) for row in pyogrio.list_layers(content)}
        if layer not in layers:
            return []
        _, _, geometries, fields = pyogrio.raw.read(
            content, layer=layer, columns=[field], X=str(x), Y=str(y), Z=str(z)
        )
    except Exception as exc:  # GDAL raises its own errors for unreadable bytes
        raise VectorTileError(f"not a readable vector tile: {exc}") from exc
    values = [_number(v) for v in fields[0]] if fields else [None] * len(geometries)
    chosen: list[Any] = [
        g
        for g, v in zip(geometries, values, strict=True)
        if g is not None and v is not None and v >= minimum
    ]
    # A tile may hold a point or a line among the enclosures (seen at 12/2012/1588): it has
    # no area to burn, so it is left out; a polygon that cannot be read still fails.
    return [wkb_polygon(bytes(g)) for g in chosen if _kind(bytes(g)) in _AREAS]


def _kind(data: bytes) -> int | None:
    try:
        return _Reader(data).header()
    except struct.error, IndexError:
        return None


__all__ = ["VectorTileError", "polygons_at_least", "wkb_polygon"]
