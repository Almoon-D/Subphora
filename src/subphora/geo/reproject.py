# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Reprojection between CRSs, honouring each CRS's own axis order.

Services answer in the axis order their CRS defines: EPSG:4326 is latitude, longitude;
EPSG:25830 is easting, northing. pyproj reads that order from the CRS definition, so a
response is reprojected from whatever ``srsName`` it declares, never from the CRS asked for.
"""

from collections.abc import Sequence
from functools import lru_cache

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError

from subphora.domain.parcels import Polygon, Position

# GeoJSON's CRS: WGS 84 in longitude, latitude order (RFC 7946).
_LON_LAT = "OGC:CRS84"

type Coordinates = Sequence[tuple[float, float]]


class ReprojectionError(ValueError):
    """An unknown CRS, or a position that cannot be reprojected."""


@lru_cache(maxsize=32)
def _transformer(source: str, target: str) -> Transformer:
    try:
        return Transformer.from_crs(CRS.from_user_input(source), CRS.from_user_input(target))
    except CRSError as exc:
        raise ReprojectionError(f"unknown CRS {source!r} or {target!r}") from exc


def _transform(coordinates: Coordinates, source: str, target: str) -> tuple[Position, ...]:
    transformer = _transformer(source, target)
    if not coordinates:
        return ()
    first, second = zip(*coordinates, strict=True)
    try:
        out_first, out_second = transformer.transform(first, second, errcheck=True)
    except ProjError as exc:
        raise ReprojectionError(f"cannot reproject from {source} to {target}: {exc}") from exc
    return tuple((float(a), float(b)) for a, b in zip(out_first, out_second, strict=True))


def to_lon_lat(coordinates: Coordinates, source: str) -> tuple[Position, ...]:
    """Positions given in ``source``'s own axis order, as (longitude, latitude)."""
    return _transform(coordinates, source, _LON_LAT)


def transform_point(position: Position, target: str) -> tuple[float, float]:
    """A (longitude, latitude) position in ``target``'s own axis order."""
    return _transform([position], _LON_LAT, target)[0]


def bbox_of(polygons: Sequence[Polygon]) -> tuple[float, float, float, float]:
    """West, south, east, north of every position of every polygon."""
    lons = [lon for polygon in polygons for ring in polygon for lon, _ in ring]
    lats = [lat for polygon in polygons for ring in polygon for _, lat in ring]
    if not lons:
        raise ValueError("no positions to bound")
    return (min(lons), min(lats), max(lons), max(lats))
