# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The explanation of one cell: the same arithmetic as the grids, as a domain estimate.

The cell is evaluated as a one-cell grid by ``evaluate``, so the explanation can never
disagree with the published index and confidence of the same build.
"""

import math
from collections.abc import Mapping, Sequence

import numpy as np

from subphora.config.model import BreaksLookup, ModelSettings
from subphora.domain.potential import (
    ComponentId,
    Confidence,
    ConfidenceComponent,
    Contribution,
    InputSource,
    InputValue,
    MissingInput,
    MissingReason,
    PotentialEstimate,
    Variable,
)
from subphora.model.evaluate import ABSENT, Category, InputGrids, Quality, evaluate, label

# Variables that are distances, capped at the build's buffer ("at least this far").
DISTANCES: frozenset[Variable] = frozenset(
    {Variable.DRAINAGE_DISTANCE_M, Variable.WATER_POINT_DISTANCE_M}
)


def _value(
    variable: Variable,
    raw: float,
    unit: str | None,
    categories: Sequence[Category],
    distance_cap_m: float,
) -> InputValue:
    if unit is not None:
        return InputValue(
            number=raw,
            unit=unit,
            at_least=variable in DISTANCES and raw >= distance_cap_m,
        )
    code = int(raw)
    if code == ABSENT:
        return InputValue(absent=True)
    category = categories[code]
    return InputValue(category=category.cls, label=category.label)


def explain_cell(
    model: ModelSettings,
    values: Mapping[Variable, float],
    categories: Mapping[Variable, Sequence[Category]],
    quality: Mapping[str, Quality],
    sources: Mapping[str, InputSource],
    evidence_distance_m: float,
    distance_cap_m: float,
) -> PotentialEstimate:
    """``values`` are the cell's raw inputs (NaN where none); ``quality`` and ``sources``
    are per criterion with an input."""
    grids = InputGrids(
        values={v: np.array([value], dtype=np.float64) for v, value in values.items()},
        categories=categories,
    )
    result = evaluate(model, grids, quality, np.array([evidence_distance_m]))
    present = [
        c
        for c in model.criteria
        if c.variable is not None and not math.isnan(float(result.suitability[c.id][0]))
    ]
    present_weight = sum(c.weight for c in present)
    contributions = []
    for criterion in present:
        variable = criterion.variable
        if variable is None:  # pragma: no cover - `present` holds only criteria with one
            continue
        suit = float(result.suitability[criterion.id][0])
        share = criterion.weight / present_weight
        unit = criterion.lookup.unit if isinstance(criterion.lookup, BreaksLookup) else None
        contributions.append(
            Contribution(
                criterion=criterion.id,
                weight=criterion.weight,
                share=share,
                value=_value(
                    variable,
                    values[variable],
                    unit,
                    categories.get(variable, ()),
                    distance_cap_m,
                ),
                suitability=suit,
                contribution=share * suit,
                source=sources[criterion.id],
            )
        )
    present_ids = {c.id for c in present}
    missing = tuple(
        MissingInput(
            criterion=c.id,
            weight=c.weight,
            reason=MissingReason.NO_DATASET if c.variable is None else MissingReason.NO_DATA,
        )
        for c in model.criteria
        if c.id not in present_ids
    )
    settings = model.confidence
    components = tuple(
        ConfidenceComponent(
            id=component,
            weight=settings.weights[component],
            value=float(grid[0]),
            measured=component is not ComponentId.SKILL,
        )
        for component, grid in result.components.items()
    )
    value = sum(c.weight * c.value for c in components)
    score = sum(c.contribution for c in contributions) if contributions else None
    return PotentialEstimate(
        score=score,
        confidence=Confidence(value=value, label=label(value, settings), components=components),
        contributions=tuple(contributions),
        missing=missing,
    )
