# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Candidate spots and the area's means (MASTER_PLAN §4.3).

- Candidates: the cells of the area with the highest index among those whose confidence
  reaches the minimum, each at least the minimum separation from every better one. Equal
  indices are ordered by confidence, then north to south and west to east.
- The area's means over its scored cells: the index, each criterion's share of the weight
  (zero where its input is missing) and contribution, the share of cells where each input
  is present, and the confidence components. Means are linear, so the mean index is the
  sum of the mean contributions, as at a cell.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import ModelSettings
from subphora.domain.potential import ComponentId
from subphora.model.evaluate import Evaluation

type Mask = NDArray[np.bool_]


def select_candidates(
    index: NDArray[np.floating],
    confidence: NDArray[np.floating],
    inside: Mask,
    cell_m: float,
    count: int,
    min_confidence: float,
    min_separation_m: float,
) -> list[tuple[int, int]]:
    """The (row, column) of up to ``count`` candidates, best first."""
    eligible = inside & ~np.isnan(index) & (np.nan_to_num(confidence, nan=-1.0) >= min_confidence)
    rows, columns = np.nonzero(eligible)
    if rows.size == 0:
        return []
    # lexsort sorts by its last key first: index, then confidence, both descending; the
    # row-major position (nonzero's order) breaks the remaining ties.
    order = np.lexsort((-confidence[rows, columns], -index[rows, columns]))
    chosen: list[tuple[int, int]] = []
    separation_cells = min_separation_m / cell_m
    for position in order:
        row, column = int(rows[position]), int(columns[position])
        if all(np.hypot(row - r, column - c) >= separation_cells for r, c in chosen):
            chosen.append((row, column))
            if len(chosen) == count:
                break
    return chosen


@dataclass(frozen=True, slots=True)
class CriterionMeans:
    mean_share: float
    mean_contribution: float
    present_share: float


@dataclass(frozen=True, slots=True)
class AreaMeans:
    cells: int
    scored_cells: int
    # None when no cell of the area is scored.
    mean_index: float | None
    mean_confidence: float | None
    components: dict[ComponentId, float]
    # Per criterion present at some scored cell.
    criteria: dict[str, CriterionMeans]


def area_means(model: ModelSettings, evaluation: Evaluation, inside: Mask) -> AreaMeans:
    scored = inside & ~np.isnan(evaluation.index)
    cells = int(inside.sum())
    count = int(scored.sum())
    if count == 0:
        return AreaMeans(cells, 0, None, None, {}, {})
    weights = {c.id: c.weight for c in model.criteria}
    present = {
        criterion: ~np.isnan(suitability[scored])
        for criterion, suitability in evaluation.suitability.items()
    }
    present_weight = sum(
        (np.where(mask, weights[criterion], 0.0) for criterion, mask in present.items()),
        np.zeros(count),
    )
    criteria = {}
    for criterion, mask in present.items():
        if not mask.any():
            continue
        share = np.where(mask, weights[criterion] / present_weight, 0.0)
        suitability = np.nan_to_num(evaluation.suitability[criterion][scored], nan=0.0)
        criteria[criterion] = CriterionMeans(
            mean_share=float(share.mean()),
            mean_contribution=float((share * suitability).mean()),
            present_share=float(mask.mean()),
        )
    components = {
        component: float(np.asarray(grid)[scored].mean())
        for component, grid in evaluation.components.items()
    }
    return AreaMeans(
        cells=cells,
        scored_cells=count,
        mean_index=float(evaluation.index[scored].mean()),
        mean_confidence=float(evaluation.confidence[scored].mean()),
        components=components,
        criteria=criteria,
    )
