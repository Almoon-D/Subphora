# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Learning from the owner's wells (MASTER_PLAN §4.3 Learning, decision 0040).

The map's value at a cell (the calibrated probability where its domain is calibrated,
otherwise the index) is the mean of a Beta prior worth ``prior_strength`` wells. Each well
whose outcome is known adds its weight to the productive or the dry count; the weight is
1 at the well, halves every ``half_weight_m`` and is 0 beyond ``range_m``. The updated
value is the posterior mean:

    (n p + W_productive) / (n + W_productive + W_dry)

and its interval the posterior's central quantiles. Far from every well nothing moves; a
productive well raises its neighbourhood, a dry one lowers it, never past 0 or 1. An index
updated this way is still an index: the arithmetic does not make it a probability.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.special import betaincinv

from subphora.config.wells import UpdateSettings
from subphora.domain.wells import WellEvidence, WellOutcome, WellUpdate

type Floats = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class KnownWell:
    """A well that is evidence: its id, outcome and position in the grid's CRS."""

    id: str
    outcome: Literal[WellOutcome.PRODUCTIVE, WellOutcome.DRY]
    x: float
    y: float


def weight(distance_m: Floats, settings: UpdateSettings) -> Floats:
    """Each distance's weight: 1 at the well, half every ``half_weight_m``, 0 beyond
    ``range_m``."""
    distance = np.asarray(distance_m, dtype=np.float64)
    result: Floats = np.where(
        distance <= settings.range_m, np.power(0.5, distance / settings.half_weight_m), 0.0
    )
    return result


def _prior(value: Floats, settings: UpdateSettings) -> Floats:
    margin = settings.prior_margin
    result: Floats = np.clip(value, margin, 1 - margin)
    return result


def posterior_mean(
    prior: Floats, productive: Floats, dry: Floats, settings: UpdateSettings
) -> Floats:
    """The updated value from the prior and the summed weights of each outcome; NaN where
    the prior is NaN (no value there to update)."""
    n = settings.prior_strength
    p = _prior(prior, settings)
    result: Floats = (n * p + productive) / (n + productive + dry)
    return result


def update_grid(
    prior: NDArray[np.floating],
    west: float,
    north: float,
    cell_m: float,
    wells: Sequence[KnownWell],
    settings: UpdateSettings,
) -> NDArray[np.float32]:
    """The grid updated with the wells (positions in the grid's CRS, cell centres from its
    north-west corner). Each well touches only the cells within its range."""
    values = np.asarray(prior, dtype=np.float64)
    height, width = values.shape
    productive = np.zeros_like(values)
    dry = np.zeros_like(values)
    reach = settings.range_m
    for well in wells:
        first_column = max(0, int(np.floor((well.x - reach - west) / cell_m)))
        last_column = min(width, int(np.ceil((well.x + reach - west) / cell_m)) + 1)
        first_row = max(0, int(np.floor((north - (well.y + reach)) / cell_m)))
        last_row = min(height, int(np.ceil((north - (well.y - reach)) / cell_m)) + 1)
        if first_column >= last_column or first_row >= last_row:
            continue
        xs = west + (np.arange(first_column, last_column) + 0.5) * cell_m
        ys = north - (np.arange(first_row, last_row) + 0.5) * cell_m
        distance = np.hypot(xs[None, :] - well.x, ys[:, None] - well.y)
        target = productive if well.outcome is WellOutcome.PRODUCTIVE else dry
        target[first_row:last_row, first_column:last_column] += weight(distance, settings)
    updated = posterior_mean(values, productive, dry, settings)
    # Where no well weighs, the map's own value, unclipped.
    return np.where(productive + dry > 0, updated, values).astype(np.float32)


def update_at(
    prior: float,
    kind: Literal["index", "probability"],
    x: float,
    y: float,
    wells: Sequence[KnownWell],
    settings: UpdateSettings,
) -> WellUpdate:
    """The value at one point updated with the wells, with its interval and every well
    that weighs there, nearest first."""
    evidence = []
    for well in wells:
        distance = float(np.hypot(well.x - x, well.y - y))
        w = float(weight(np.array([distance]), settings)[0])
        if w > 0:
            evidence.append(
                WellEvidence(well_id=well.id, outcome=well.outcome, distance_m=distance, weight=w)
            )
    evidence.sort(key=lambda e: (e.distance_m, e.well_id))
    productive = sum(e.weight for e in evidence if e.outcome is WellOutcome.PRODUCTIVE)
    dry = sum(e.weight for e in evidence if e.outcome is WellOutcome.DRY)
    n = settings.prior_strength
    p = float(_prior(np.array([prior]), settings)[0])
    a, b = n * p + productive, n * (1 - p) + dry
    value = a / (a + b) if evidence else prior
    tail = (1 - settings.level) / 2
    low, high = (float(q) for q in betaincinv(a, b, np.array([tail, 1 - tail])))
    return WellUpdate(
        kind=kind,
        prior=prior,
        value=value,
        low=min(low, value),
        high=max(high, value),
        level=settings.level,
        prior_strength=n,
        half_weight_m=settings.half_weight_m,
        range_m=settings.range_m,
        evidence=tuple(evidence),
    )
