# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The explanation of one cell: the same arithmetic as the grids, as a domain estimate.

The cell is evaluated as a one-cell grid by ``evaluate``, so the explanation can never
disagree with the published index and confidence of the same build.
"""

import math
from collections.abc import Mapping, Sequence

import numpy as np

from subphora.config.model import BreaksLookup, ConfidenceSettings, ModelSettings
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


def _value(
    variable: Variable,
    raw: float,
    unit: str | None,
    categories: Sequence[Category],
    distance_caps_m: Mapping[Variable, float],
) -> InputValue:
    if unit is not None:
        cap = distance_caps_m.get(variable)
        return InputValue(number=raw, unit=unit, at_least=cap is not None and raw >= cap)
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
    distance_caps_m: Mapping[Variable, float],
) -> PotentialEstimate:
    """``values`` are the cell's raw inputs (NaN where none; a variable left out has no
    input at this scale); ``quality`` and ``sources`` are per criterion whose variable is
    among them; a distance at its cap in ``distance_caps_m`` is "at least" that far."""
    grids = InputGrids(
        values={v: np.array([value], dtype=np.float64) for v, value in values.items()},
        categories=categories,
    )
    result = evaluate(model, grids, quality, np.array([evidence_distance_m]))
    present = [
        c
        for c in model.criteria
        if c.id in result.suitability and not math.isnan(float(result.suitability[c.id][0]))
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
                    distance_caps_m,
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
            reason=MissingReason.NO_DATASET
            if c.variable is None or c.variable not in values
            else MissingReason.NO_DATA,
        )
        for c in model.criteria
        if c.id not in present_ids
    )
    score = sum(c.contribution for c in contributions) if contributions else None
    return PotentialEstimate(
        score=score,
        confidence=confidence_of(
            {component: float(grid[0]) for component, grid in result.components.items()},
            model.confidence,
        ),
        contributions=tuple(contributions),
        missing=missing,
    )


def confidence_of(values: Mapping[ComponentId, float], settings: ConfidenceSettings) -> Confidence:
    """The confidence of its component values: their weighted sum and its label. The
    model's skill is not measured until session 07."""
    components = tuple(
        ConfidenceComponent(
            id=component,
            weight=settings.weights[component],
            value=value,
            measured=component is not ComponentId.SKILL,
        )
        for component, value in values.items()
    )
    value = sum(c.weight * c.value for c in components)
    return Confidence(value=value, label=label(value, settings), components=components)
