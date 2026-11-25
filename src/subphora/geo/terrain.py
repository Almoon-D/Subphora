# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Terrain derivatives on a grid window: slope, upstream area, wetness, distance to drainage.

- Slope: Horn's 3x3 finite differences (Horn 1981), in degrees; a neighbour without
  elevation (the sea, the window's edge) counts as level with the cell.
- Flow: depressions filled and D8 directions by pyflwdir (priority flood, flats routed to
  their outlets), outlets at the edge of the valid cells; upstream area in km².
- Wetness: the topographic wetness index ln(a / tan b) (Beven and Kirkby 1979), with a the
  upstream area per unit contour width (one cell) and b at least ``min_slope_deg``.
- Drainage: cells whose upstream area reaches the channel threshold, and each cell's
  distance to the nearest of them.
"""

from dataclasses import dataclass

import numpy as np
import pyflwdir
from numpy.typing import NDArray

from subphora.geo.grid import GridWindow
from subphora.geo.raster import FloatGrid, distance_to

_NODATA = -9999.0
_SQUARE_METRES_PER_KM2 = 1e6


@dataclass(frozen=True, slots=True)
class Terrain:
    slope_deg: FloatGrid
    upstream_km2: FloatGrid
    twi: FloatGrid
    drainage_distance_m: FloatGrid


def slope_degrees(elevation: FloatGrid, cell_m: float) -> FloatGrid:
    z = np.pad(elevation.astype(np.float64), 1, constant_values=np.nan)
    centre = z[1:-1, 1:-1]

    def at(rows: slice, columns: slice) -> NDArray[np.float64]:
        # A neighbour without elevation (the sea, the window's edge) counts as level.
        neighbour = z[rows, columns]
        return np.where(np.isnan(neighbour), centre, neighbour)

    before, middle, after = slice(None, -2), slice(1, -1), slice(2, None)
    a, b, c = at(before, before), at(before, middle), at(before, after)
    d, f = at(middle, before), at(middle, after)
    g, h, i = at(after, before), at(after, middle), at(after, after)
    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell_m)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cell_m)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype(np.float32)


def upstream_area_km2(elevation: FloatGrid, window: GridWindow) -> FloatGrid:
    valid = ~np.isnan(elevation)
    if not valid.any():
        return np.full(elevation.shape, np.nan, dtype=np.float32)
    dem = np.where(valid, elevation, _NODATA).astype(np.float32)
    flow = pyflwdir.from_dem(dem, nodata=_NODATA, transform=window.transform, latlon=False)
    area = np.asarray(flow.upstream_area(unit="km2"), dtype=np.float32)
    return np.where(valid, area, np.nan).astype(np.float32)


def wetness_index(
    upstream_km2: FloatGrid, slope_deg: FloatGrid, cell_m: float, min_slope_deg: float
) -> FloatGrid:
    specific_area = upstream_km2.astype(np.float64) * _SQUARE_METRES_PER_KM2 / cell_m
    tan_slope = np.tan(np.radians(np.maximum(slope_deg.astype(np.float64), min_slope_deg)))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.log(specific_area / tan_slope).astype(np.float32)


def derive(
    elevation: FloatGrid,
    window: GridWindow,
    channel_area_km2: float,
    min_slope_deg: float,
    distance_cap_m: float,
) -> Terrain:
    slope = slope_degrees(elevation, window.cell_m)
    upstream = upstream_area_km2(elevation, window)
    channels: NDArray[np.bool_] = np.nan_to_num(upstream, nan=0.0) >= channel_area_km2
    drainage = distance_to(channels, window.cell_m, distance_cap_m)
    return Terrain(
        slope_deg=slope,
        upstream_km2=upstream,
        twi=wetness_index(upstream, slope, window.cell_m, min_slope_deg),
        drainage_distance_m=np.where(np.isnan(elevation), np.nan, drainage).astype(np.float32),
    )
