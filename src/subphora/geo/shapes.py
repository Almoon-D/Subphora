# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Outlines in longitude and latitude: geodesic area, a point inside, simple rings.

The area is measured on the GRS80 ellipsoid by pyproj (ETRS89's ellipsoid; WGS 84's differs
by a fraction of a millimetre on the minor axis). Holes count against their polygon.
"""

from collections.abc import Sequence
from functools import lru_cache
from itertools import pairwise

from pyproj import Geod

from subphora.domain.parcels import Polygon, Position
from subphora.geo.areas import contains

_ELLIPSOID = "GRS80"
# A closed ring repeats its first position: at least three distinct ones and the repeat.
_MIN_RING_POSITIONS = 4


class ShapeError(ValueError):
    """An outline that is not a simple, closed polygon with an area."""


@lru_cache(maxsize=1)
def _geod() -> Geod:
    return Geod(ellps=_ELLIPSOID)


def _ring_area(ring: Sequence[Position]) -> float:
    lons = [lon for lon, _ in ring]
    lats = [lat for _, lat in ring]
    area, _perimeter = _geod().polygon_area_perimeter(lons, lats)
    return abs(float(area))


def geodesic_area_m2(polygons: Sequence[Polygon]) -> float:
    """The area in square metres: outer rings minus their holes."""
    total = 0.0
    for polygon in polygons:
        outer, *holes = polygon
        total += _ring_area(outer) - sum(_ring_area(hole) for hole in holes)
    return total


def _centroid(ring: Sequence[Position]) -> Position | None:
    """The planar centroid of a ring in degrees (good enough to find a point inside)."""
    twice_area = cx = cy = 0.0
    for (x1, y1), (x2, y2) in pairwise(ring):
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if twice_area == 0:
        return None
    return (cx / (3 * twice_area), cy / (3 * twice_area))


def point_inside(polygons: Sequence[Polygon]) -> Position:
    """A point of the largest polygon: its centroid when inside it, else a vertex."""
    largest = max(polygons, key=lambda polygon: _ring_area(polygon[0]))
    centroid = _centroid(largest[0])
    if centroid is not None and contains((largest,), *centroid):
        return centroid
    return largest[0][0]


def _segments_cross(a: Position, b: Position, c: Position, d: Position) -> bool:
    """Whether segments ab and cd share a point (touching counts)."""

    def orientation(p: Position, q: Position, r: Position) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: Position, q: Position, r: Position) -> bool:
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(
            p[1], r[1]
        )

    o1, o2, o3, o4 = (
        orientation(a, b, c),
        orientation(a, b, d),
        orientation(c, d, a),
        orientation(c, d, b),
    )
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and 0 not in (o1, o2, o3, o4):
        return True
    return (
        (o1 == 0 and on_segment(a, c, b))
        or (o2 == 0 and on_segment(a, d, b))
        or (o3 == 0 and on_segment(c, a, d))
        or (o4 == 0 and on_segment(c, b, d))
    )


def check_simple_ring(ring: Sequence[Position]) -> None:
    """Raise ShapeError unless the ring is closed, has three distinct vertices, encloses an
    area and never crosses or touches itself."""
    if len(ring) < _MIN_RING_POSITIONS or ring[0] != ring[-1]:
        raise ShapeError("a polygon is a closed ring of at least three points")
    vertices = list(ring[:-1])
    if len(set(vertices)) != len(vertices):
        raise ShapeError("a polygon passes twice through the same point")
    if _centroid(ring) is None:
        raise ShapeError("a polygon encloses no area")
    count = len(vertices)
    edges = [(vertices[i], vertices[(i + 1) % count]) for i in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            # Neighbouring edges share a vertex by construction.
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if _segments_cross(*edges[i], *edges[j]):
                raise ShapeError("a polygon whose sides cross")
