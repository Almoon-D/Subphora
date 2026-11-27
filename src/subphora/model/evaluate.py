# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Suitability, score and confidence over whole grids (or one cell, as a 1-cell grid).

- Each criterion's input becomes a 0-1 suitability by its lookup; a cell where the input
  has no value, or a category the lookup does not list, is missing there (NaN), never
  filled in. A criterion whose variable is not among the grids (no input at this scale)
  is missing everywhere.
- The index is the weighted mean of the suitabilities present: the weights renormalised
  over the criteria present at that cell. No input present: no index (NaN).
- A criterion admitted by validation (``admission: validated``) counts only in the cells
  of ``admitted``: elsewhere it is not part of the model at all, neither in the index nor
  in the weight the coverage is measured against.
- Confidence is the weighted sum of five components (coverage, resolution, age,
  evidence, skill); a cell without an index has no confidence either. The skill is the
  measured skill of the cell's domain, or ``skill_not_measured`` where it has none.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import (
    BreaksLookup,
    ClassesLookup,
    ConfidenceSettings,
    Criterion,
    ModelSettings,
)
from subphora.domain.potential import ComponentId, ConfidenceLabel, Variable

type Grid = NDArray[np.float64]
# A categorical grid holds a code into its category list; this code means no feature.
ABSENT = -1


@dataclass(frozen=True, slots=True)
class Category:
    """One category of a categorical input: the class its lookup reads, and its label."""

    cls: str
    label: str


@dataclass(frozen=True, slots=True)
class Quality:
    """How well an input's resolution fits the cell, and how recent it is (each 0-1)."""

    resolution: float
    age: float


@dataclass(frozen=True, slots=True)
class InputGrids:
    """The input variables on one grid, NaN where outside the region or without data."""

    values: Mapping[Variable, NDArray[np.floating]]
    categories: Mapping[Variable, Sequence[Category]]


@dataclass(frozen=True, slots=True)
class Evaluation:
    suitability: dict[str, Grid]
    index: Grid
    confidence: Grid
    components: dict[ComponentId, Grid]


def suitability(
    criterion: Criterion, values: NDArray[np.floating], categories: Sequence[Category] = ()
) -> Grid:
    """The criterion's 0-1 suitability; NaN where its input is missing."""
    lookup = criterion.lookup
    data = np.asarray(values, dtype=np.float64)
    if isinstance(lookup, BreaksLookup):
        index = np.digitize(np.nan_to_num(data, nan=0.0), lookup.breaks, right=False)
        result = np.asarray(lookup.values, dtype=np.float64)[index]
        return np.where(np.isnan(data), np.nan, result)
    if isinstance(lookup, ClassesLookup):
        by_code = np.array(
            [lookup.classes.get(category.cls, np.nan) for category in categories] + [np.nan],
            dtype=np.float64,
        )
        codes = np.nan_to_num(data, nan=-2.0).astype(np.int64)
        valid = (codes >= 0) & (codes < len(categories))
        result = by_code[np.where(valid, codes, len(categories))]
        absent = np.nan if lookup.absent is None else lookup.absent
        return np.where(codes == ABSENT, absent, result)
    raise ValueError(f"{criterion.id} has no input")


def label(value: float, settings: ConfidenceSettings) -> ConfidenceLabel:
    if value >= settings.thresholds.high:
        return ConfidenceLabel.HIGH
    if value >= settings.thresholds.medium:
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LOW


def evidence_component(distance_m: Grid, settings: ConfidenceSettings) -> Grid:
    """1 within the full distance, falling linearly to 0 at the far one; 0 where unknown."""
    full = settings.evidence_full_within_m
    none = settings.evidence_none_beyond_m
    value = np.clip((none - distance_m) / (none - full), 0.0, 1.0)
    return np.where(np.isnan(distance_m), 0.0, value)


def evaluate(
    model: ModelSettings,
    grids: InputGrids,
    quality: Mapping[str, Quality],
    evidence_distance_m: NDArray[np.floating],
    skill: NDArray[np.floating] | None = None,
    admitted: Mapping[str, NDArray[np.bool_]] | None = None,
) -> Evaluation:
    """Index and confidence on the grids; ``quality`` per criterion whose variable is
    among the grids; ``skill`` per cell, NaN (or no grid) where its domain is unmeasured;
    ``admitted`` per criterion admitted by validation, the cells where it is part of the
    model (a criterion left out is admitted nowhere)."""
    shape = np.shape(evidence_distance_m)
    admitted = admitted or {}
    total_weight = np.full(shape, sum(c.weight for c in model.criteria if not c.gated))
    for criterion in model.gated:
        if criterion.id in admitted:
            total_weight = total_weight + np.where(admitted[criterion.id], criterion.weight, 0.0)
    weighted = np.zeros(shape)
    present_weight = np.zeros(shape)
    resolution = np.zeros(shape)
    age = np.zeros(shape)
    suitabilities: dict[str, Grid] = {}
    for criterion in model.criteria:
        # No input at any scale, or none at this one (the faults on the national map).
        if criterion.variable is None or criterion.variable not in grids.values:
            continue
        if criterion.gated and criterion.id not in admitted:
            continue
        values = grids.values[criterion.variable]
        suit = suitability(criterion, values, grids.categories.get(criterion.variable, ()))
        if criterion.gated:
            suit = np.where(admitted[criterion.id], suit, np.nan)
        suitabilities[criterion.id] = suit
        present = ~np.isnan(suit)
        weight = np.where(present, criterion.weight, 0.0)
        weighted += np.where(present, criterion.weight * suit, 0.0)
        present_weight += weight
        resolution += weight * quality[criterion.id].resolution
        age += weight * quality[criterion.id].age
    has_input = present_weight > 0
    safe = np.where(has_input, present_weight, 1.0)
    index = np.where(has_input, weighted / safe, np.nan)
    settings = model.confidence
    components = {
        ComponentId.COVERAGE: present_weight / total_weight,
        ComponentId.RESOLUTION: np.where(has_input, resolution / safe, 0.0),
        ComponentId.AGE: np.where(has_input, age / safe, 0.0),
        ComponentId.EVIDENCE: evidence_component(
            np.asarray(evidence_distance_m, dtype=np.float64), settings
        ),
        ComponentId.SKILL: np.full(shape, settings.skill_not_measured)
        if skill is None
        else np.where(
            np.isnan(np.asarray(skill, dtype=np.float64)),
            settings.skill_not_measured,
            np.asarray(skill, dtype=np.float64),
        ),
    }
    confidence = sum(
        (settings.weights[component] * grid for component, grid in components.items()),
        np.zeros(shape),
    )
    return Evaluation(
        suitability=suitabilities,
        index=index,
        confidence=np.where(has_input, confidence, np.nan),
        components=components,
    )
