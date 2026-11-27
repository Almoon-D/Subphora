# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The depth to water at a spot and the cost of drilling to it (MASTER_PLAN §4.3).

- The water table is interpolated only from piezometers of the spot's own groundwater
  body: inverse-distance weighting of the nearest ones within the maximum distance. A
  piezometer of another body is never used, however near.
- Its range is the piezometers' weighted seasonal half-range, widened with the distance to
  the nearest one; past the maximum distance the depth is "unknown".
- The owner's wells read at rest are points like the piezometers, of their own body, that
  carry the well's id instead of a public source: the estimate lists them apart.
- Depth = ground elevation (the terrain model) - water table, never below 0; the range
  follows from the water table's. Carbonate rock (possible karst) is flagged.
- The same rules give a depth grid over a whole area (``depth_grid``), for the export
  pack; a cell where the depth is unknown has no value there.
- Cost = metres drilled (depth range + the drilling below the water table) x cost per
  metre + fixed costs, in ``Decimal`` euros rounded to the euro.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from subphora.config.depth import DrillingSettings, WaterTableSettings
from subphora.domain.depth import (
    DepthEstimate,
    DepthUnknown,
    DrillingCost,
    LevelsSource,
    OwnLevel,
    WaterTable,
)

# Nearer than this, a piezometer stands at the spot: its level is taken alone.
_AT_SPOT_M = 1.0
_EURO = Decimal(1)
_DECIMETRE = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class PiezometerPoint:
    """A piezometer in the grid's CRS, with its level and seasonal range (m a.s.l.)."""

    x: float
    y: float
    body: str
    level_m: float
    low_m: float
    high_m: float
    # The services of the levels it summarises.
    sources: tuple[str, ...] = ()
    # The owner's well it is, for a private level (no public source).
    well_id: str | None = None


def _nearest(
    x: float,
    y: float,
    body: str,
    piezometers: Sequence[PiezometerPoint],
    settings: WaterTableSettings,
) -> list[tuple[float, PiezometerPoint]]:
    """``body``'s piezometers used at (x, y): the nearest within the maximum distance, or
    the one at the spot alone."""
    near = sorted(
        ((math.hypot(p.x - x, p.y - y), p) for p in piezometers if p.body == body),
        key=lambda pair: pair[0],
    )
    near = [pair for pair in near if pair[0] <= settings.max_distance_m][: settings.max_piezometers]
    return near[:1] if near and near[0][0] < _AT_SPOT_M else near


def water_table(
    x: float,
    y: float,
    body: str,
    body_label: str,
    piezometers: Sequence[PiezometerPoint],
    settings: WaterTableSettings,
) -> WaterTable | None:
    """The water table at (x, y) from ``body``'s piezometers; None when none is within the
    maximum distance."""
    near = _nearest(x, y, body, piezometers, settings)
    if not near:
        return None
    nearest = near[0][0]
    weights = [1.0 if d < _AT_SPOT_M else 1 / d**settings.power for d, _ in near]
    total = sum(weights)
    level = sum(w * p.level_m for w, (_, p) in zip(weights, near, strict=True)) / total
    spread = (
        sum(w * (p.high_m - p.low_m) / 2 for w, (_, p) in zip(weights, near, strict=True)) / total
    )
    half = spread + settings.growth_m_per_km * nearest / 1000
    return WaterTable(
        elevation_m=level,
        low_m=level - half,
        high_m=level + half,
        body=body,
        body_label=body_label,
        piezometers=len(near),
        nearest_m=nearest,
    )


def depth_at(
    x: float,
    y: float,
    ground_m: float,
    body: tuple[str, str] | None,
    piezometers: Sequence[PiezometerPoint],
    settings: WaterTableSettings,
    karst: bool,
    sources: Mapping[str, LevelsSource] | None,
    own: Mapping[str, OwnLevel] | None = None,
) -> DepthEstimate:
    """The depth to water at a spot; ``body`` is its groundwater body (code, label) or
    None outside every body; ``sources`` (by service) is None when no levels were
    imported; ``own`` holds the owner's private levels (by well id) among the points."""

    def unknown(reason: DepthUnknown) -> DepthEstimate:
        return DepthEstimate(state="unknown", reason=reason, karst=karst)

    own = own or {}
    if sources is None and not own:
        return unknown(DepthUnknown.NOT_IMPORTED)
    if body is None:
        return unknown(DepthUnknown.OUTSIDE_BODIES)
    if math.isnan(ground_m):
        return unknown(DepthUnknown.NO_GROUND_ELEVATION)
    table = water_table(x, y, body[0], body[1], piezometers, settings)
    if table is None:
        return unknown(DepthUnknown.NO_PIEZOMETER_NEARBY)
    near = _nearest(x, y, body[0], piezometers, settings)
    used = {s for _, p in near for s in p.sources}
    wells = [
        own[p.well_id].model_copy(update={"distance_m": d})
        for d, p in near
        if p.well_id is not None and p.well_id in own
    ]
    return DepthEstimate(
        state="estimated",
        ground_m=ground_m,
        water_table=table,
        depth_m=max(0.0, ground_m - table.elevation_m),
        low_m=max(0.0, ground_m - table.high_m),
        high_m=max(0.0, ground_m - table.low_m),
        karst=karst,
        sources=tuple(s for key, s in (sources or {}).items() if key in used),
        own_levels=tuple(wells),
    )


@dataclass(frozen=True, slots=True)
class DepthGrid:
    """Metres below ground to the water table at each cell, with its range; NaN where the
    depth is unknown."""

    depth: NDArray[np.float32]
    low: NDArray[np.float32]
    high: NDArray[np.float32]


def depth_grid(
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    ground: NDArray[np.float32],
    body_codes: NDArray[np.float32],
    body_ids: Sequence[str],
    piezometers: Sequence[PiezometerPoint],
    settings: WaterTableSettings,
) -> DepthGrid:
    """``depth_at`` at every cell: ``xs`` and ``ys`` are the cells' centres, ``body_codes``
    the index of each cell's body in ``body_ids`` (-1 or NaN outside every body)."""
    shape = ground.shape
    depth = np.full(shape, np.nan, dtype=np.float32)
    low = np.full(shape, np.nan, dtype=np.float32)
    high = np.full(shape, np.nan, dtype=np.float32)
    codes = np.where(np.isnan(body_codes), -1, body_codes).astype(np.int64)
    # cKDTree's bound is strict; ``depth_at`` keeps a piezometer at exactly the maximum.
    reach = float(np.nextafter(settings.max_distance_m, math.inf))
    for code, body in enumerate(body_ids):
        points = [p for p in piezometers if p.body == body]
        cells = (codes == code) & ~np.isnan(ground)
        if not points or not cells.any():
            continue
        k = min(settings.max_piezometers, len(points))
        tree = cKDTree(np.array([(p.x, p.y) for p in points]))
        query = np.column_stack((xs[cells], ys[cells]))
        found = tree.query(query, k=k, distance_upper_bound=reach)
        distances = np.asarray(found[0], dtype=np.float64).reshape(len(query), k)
        indices = np.asarray(found[1], dtype=np.int64).reshape(len(query), k)
        used = np.isfinite(distances)
        # A piezometer at the spot is taken alone.
        used[distances[:, 0] < _AT_SPOT_M, 1:] = False
        with np.errstate(divide="ignore"):
            weights = np.where(distances < _AT_SPOT_M, 1.0, 1.0 / distances**settings.power)
        weights = np.where(used, weights, 0.0)
        safe = np.where(used, indices, 0)
        levels = np.array([p.level_m for p in points])[safe]
        halves = np.array([(p.high_m - p.low_m) / 2 for p in points])[safe]
        known = used[:, 0]
        total = np.where(known, weights.sum(axis=1), 1.0)
        level = (weights * levels).sum(axis=1) / total
        half = (weights * halves).sum(axis=1) / total + settings.growth_m_per_km * np.where(
            known, distances[:, 0], 0.0
        ) / 1000
        surface = ground[cells].astype(np.float64)
        rows = np.flatnonzero(cells.ravel())[known]
        for grid, values in (
            (depth, surface - level),
            (low, surface - (level + half)),
            (high, surface - (level - half)),
        ):
            grid.ravel()[rows] = np.maximum(0.0, values[known])
    return DepthGrid(depth=depth, low=low, high=high)


def drilling_cost(depth: DepthEstimate, settings: DrillingSettings) -> DrillingCost | None:
    """The cost range of drilling to an estimated depth; None for an unknown one."""
    if depth.state != "estimated" or depth.low_m is None or depth.high_m is None:
        return None
    below = Decimal(str(settings.below_water_table_m))
    drilled_low = (Decimal(str(depth.low_m)) + below).quantize(_DECIMETRE, ROUND_HALF_UP)
    drilled_high = (Decimal(str(depth.high_m)) + below).quantize(_DECIMETRE, ROUND_HALF_UP)
    per_metre, fixed = settings.per_metre, settings.fixed
    return DrillingCost(
        currency=settings.currency,
        low=(drilled_low * per_metre.low + fixed.low).quantize(_EURO, ROUND_HALF_UP),
        high=(drilled_high * per_metre.high + fixed.high).quantize(_EURO, ROUND_HALF_UP),
        drilled_low_m=drilled_low,
        drilled_high_m=drilled_high,
        per_metre_low=per_metre.low,
        per_metre_high=per_metre.high,
        fixed_low=fixed.low,
        fixed_high=fixed.high,
        source=settings.source,
        priced_on=settings.priced_on,
    )
