# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Official area boundaries: rounded to a common grid, and which area holds a point.

The boundaries of neighbouring areas come from one national dataset, so a shared border is
the same list of vertices in both. Rounding every vertex to the same grid keeps it the same
list: the rounded areas still meet without gaps or overlaps, while the grid drops the
detail no map tile can show. Dropping a vertex that lies exactly on the line through its
neighbours changes no shape, so shared borders stay shared after it too.

A point on a shared border belongs to exactly one of the two areas (the half-open rule of
the crossing test below), so a tap there asks one regional service, never two.
"""

from collections.abc import Sequence

type Ring = tuple[tuple[float, float], ...]
# Polygons, each an outer ring and its holes, in (longitude, latitude).
type MultiPolygon = tuple[tuple[Ring, ...], ...]
type Box = tuple[float, float, float, float]

# The fewest distinct vertices of a ring that encloses an area.
_MIN_RING_VERTICES = 3
# A position is at least a longitude and a latitude.
_POSITION = 2
# Decimals kept of a rounded coordinate: the same cell always gives the same float.
_DECIMALS = 9


class BoundaryError(ValueError):
    """A boundary that is not a polygon or multipolygon in longitude and latitude."""


def _cells(ring: Sequence[Sequence[float]], grid: float) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for vertex in ring:
        if len(vertex) < _POSITION:
            raise BoundaryError("a position needs a longitude and a latitude")
        cell = (round(float(vertex[0]) / grid), round(float(vertex[1]) / grid))
        if not cells or cells[-1] != cell:
            cells.append(cell)
    while len(cells) > 1 and cells[0] == cells[-1]:
        cells.pop()
    return _without_collinear(cells)


def _without_collinear(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    # Integer cells: the cross product is exact, so only truly collinear vertices go.
    changed = True
    while changed and len(cells) >= _MIN_RING_VERTICES:
        changed = False
        kept: list[tuple[int, int]] = []
        count = len(cells)
        for index, (x, y) in enumerate(cells):
            px, py = kept[-1] if kept else cells[index - 1]
            nx, ny = cells[(index + 1) % count]
            if (x - px) * (ny - py) - (y - py) * (nx - px) == 0:
                changed = True
                continue
            kept.append((x, y))
        cells = kept
    return cells


def _area2(cells: Sequence[tuple[int, int]]) -> int:
    return abs(
        sum(
            cells[i][0] * cells[i - 1][1] - cells[i - 1][0] * cells[i][1] for i in range(len(cells))
        )
    )


def round_to_grid(geometry: object, grid: float) -> MultiPolygon:
    """A GeoJSON Polygon or MultiPolygon rounded to ``grid`` degrees.

    Rings that collapse to nothing at the grid (islets smaller than a cell) are dropped;
    a polygon whose outer ring collapses goes with its holes.
    """
    if grid <= 0:
        raise ValueError("the grid must be positive")
    if not isinstance(geometry, dict):
        raise BoundaryError("a geometry must be an object")
    kind, coordinates = geometry.get("type"), geometry.get("coordinates")
    if not isinstance(coordinates, list):
        raise BoundaryError("a geometry without coordinates")
    match kind:
        case "Polygon":
            polygons = [coordinates]
        case "MultiPolygon":
            polygons = coordinates
        case _:
            raise BoundaryError(f"expected a Polygon or MultiPolygon, got {kind!r}")
    result: list[tuple[Ring, ...]] = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise BoundaryError("a polygon without rings")
        rings: list[Ring] = []
        for ring in polygon:
            if not isinstance(ring, list):
                raise BoundaryError("a ring must be a list of positions")
            cells = _cells(ring, grid)
            if len(cells) < _MIN_RING_VERTICES or _area2(cells) == 0:
                if not rings:
                    break  # the outer ring vanished: so does the polygon
                continue
            rings.append(
                tuple((round(x * grid, _DECIMALS), round(y * grid, _DECIMALS)) for x, y in cells)
            )
        if rings:
            result.append(tuple(rings))
    if not result:
        raise BoundaryError("the boundary has no area at this grid")
    return tuple(result)


def bounds(area: MultiPolygon) -> Box:
    """(west, south, east, north) of every vertex."""
    xs = [x for polygon in area for ring in polygon for x, _ in ring]
    ys = [y for polygon in area for ring in polygon for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def within(inner: Box, outer: Box) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def in_box(box: Box, lon: float, lat: float) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def contains(area: MultiPolygon, lon: float, lat: float) -> bool:
    """Whether (lon, lat) is inside the area (even-odd over every ring, so holes count).

    An edge counts when it crosses the horizontal through the point with one end strictly
    above and the other at or below it, and the crossing lies strictly east of the point.
    Two areas sharing a border see the same edges, so exactly one of them holds a point on
    that border.
    """
    inside = False
    for polygon in area:
        for ring in polygon:
            previous = ring[-1]
            for current in ring:
                (x1, y1), (x2, y2) = previous, current
                if (y1 > lat) != (y2 > lat):
                    crossing = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                    if crossing > lon:
                        inside = not inside
                previous = current
    return inside
