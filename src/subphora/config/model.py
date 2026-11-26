# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/model.yaml``: the criteria, their weights and suitability
lookups (each with its source), and how confidence is computed (MASTER_PLAN §4.3)."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveFloat, model_validator

from subphora.config.base import Section
from subphora.domain.potential import CATEGORICAL, RESULTS, ComponentId, Variable

_ID = r"^[a-z0-9]+(_[a-z0-9]+)*$"
_UNIT = Field(ge=0, le=1)
_WEIGHT_SUM_TOLERANCE = 1e-9


class ClassesLookup(Section):
    """A category to a suitability; ``absent`` where the input has no feature (None: no
    data there)."""

    kind: Literal["classes"]
    classes: dict[str, Annotated[float, _UNIT]] = Field(min_length=1)
    absent: float | None = _UNIT
    source: str = Field(min_length=1)


class BreaksLookup(Section):
    """A number to ``values[i]``, where i is how many breaks are at or below it."""

    kind: Literal["breaks"]
    unit: str = Field(min_length=1)
    breaks: list[float] = Field(min_length=1)
    values: list[Annotated[float, _UNIT]]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if any(later <= earlier for earlier, later in pairwise(self.breaks)):
            raise ValueError("breaks must rise strictly")
        if len(self.values) != len(self.breaks) + 1:
            raise ValueError("a lookup has one more value than breaks")
        return self


type Lookup = Annotated[ClassesLookup | BreaksLookup, Field(discriminator="kind")]


class Criterion(Section):
    id: str = Field(pattern=_ID)
    weight: PositiveFloat = Field(le=1)
    weight_source: str = Field(min_length=1)
    # None: no nationwide input yet; the criterion is missing everywhere.
    variable: Variable | None
    lookup: Lookup | None = None

    @model_validator(mode="after")
    def _lookup_matches(self) -> Self:
        if (self.variable is None) != (self.lookup is None):
            raise ValueError(f"{self.id}: a criterion has a lookup exactly when it has a variable")
        if self.variable is None or self.lookup is None:
            return self
        if self.variable in RESULTS:
            raise ValueError(f"{self.id}: {self.variable} is a result, not an input")
        expected = "classes" if self.variable in CATEGORICAL else "breaks"
        if self.lookup.kind != expected:
            raise ValueError(f"{self.id}: {self.variable} needs a {expected} lookup")
        return self


class Ageing(Section):
    """1 up to ``full_years`` of age, falling linearly to 0 at ``zero_years``."""

    full_years: float = Field(ge=0)
    zero_years: PositiveFloat

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.zero_years <= self.full_years:
            raise ValueError("zero_years must exceed full_years")
        return self


class Thresholds(Section):
    medium: float = _UNIT
    high: float = _UNIT

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not 0 < self.medium < self.high <= 1:
            raise ValueError("thresholds must satisfy 0 < medium < high <= 1")
        return self


class ConfidenceSettings(Section):
    weights: dict[ComponentId, Annotated[float, _UNIT]]
    thresholds: Thresholds
    unknown_value: float = _UNIT
    evidence_full_within_m: float = Field(ge=0)
    evidence_none_beyond_m: PositiveFloat
    skill_not_measured: float = _UNIT
    skill_full_at_auc: float = Field(gt=0.5, le=1)
    ageing: dict[str, Ageing] = Field(min_length=1)

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if set(self.weights) != set(ComponentId):
            raise ValueError(f"confidence weights name exactly {sorted(ComponentId)}")
        if abs(sum(self.weights.values()) - 1) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError("confidence weights must add up to 1")
        if self.evidence_none_beyond_m <= self.evidence_full_within_m:
            raise ValueError("evidence_none_beyond_m must exceed evidence_full_within_m")
        return self


class ModelSettings(Section):
    criteria: list[Criterion] = Field(min_length=1)
    confidence: ConfidenceSettings

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [c.id for c in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("criterion ids must be unique")
        variables = [c.variable for c in self.criteria if c.variable is not None]
        if len(set(variables)) != len(variables):
            raise ValueError("two criteria read the same variable")
        if abs(sum(c.weight for c in self.criteria) - 1) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError("criteria weights must add up to 1")
        return self

    def criterion(self, criterion_id: str) -> Criterion:
        for criterion in self.criteria:
            if criterion.id == criterion_id:
                return criterion
        raise KeyError(criterion_id)
