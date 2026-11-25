# Copyright (c) 2026 Almoon-D. All rights reserved.
"""A water-potential estimate and its explanation (MASTER_PLAN §4.3, hard rule 1).

An estimate cannot be built without its confidence, the contribution of every input
present (its value, suitability, renormalised weight, source, date and resolution) and the
list of the inputs that are missing, with why. Until session 07 calibrates the model the
score is a relative potential index: ``kind`` admits nothing else.
"""

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.layers import LayerDetail

# Rounding the stored float32 grids leaves sums off by about this much.
_TOLERANCE = 1e-4
_UNIT = Field(ge=0, le=1)


class Variable(StrEnum):
    """A grid the national build makes: an input's values, or the model's results."""

    PERMEABILITY_CLASS = "permeability_class"
    ELEVATION_M = "elevation_m"
    SLOPE_DEG = "slope_deg"
    TWI = "twi"
    DRAINAGE_DISTANCE_M = "drainage_distance_m"
    CLAY_PCT = "clay_pct"
    GROUNDWATER_STATUS = "groundwater_status"
    WATER_POINT_DISTANCE_M = "water_point_distance_m"
    # Parcel scale only (no nationwide grid): mapped faults per area around a cell, and the
    # dip of the bedding measured nearest to it.
    LINEAMENT_DENSITY = "lineament_density"
    BEDDING_DIP_DEG = "bedding_dip_deg"
    INDEX = "index"
    CONFIDENCE = "confidence"


# Variables whose values are categories: a code into the region's category list, -1 where
# the input has no feature at the cell.
CATEGORICAL: frozenset[Variable] = frozenset(
    {Variable.PERMEABILITY_CLASS, Variable.GROUNDWATER_STATUS}
)
# Variables that are distances, capped at how far their input was read ("at least this far").
DISTANCES: frozenset[Variable] = frozenset(
    {Variable.DRAINAGE_DISTANCE_M, Variable.WATER_POINT_DISTANCE_M}
)
# The model's results, not inputs.
RESULTS: frozenset[Variable] = frozenset({Variable.INDEX, Variable.CONFIDENCE})


class InputSource(DomainModel):
    """Where an input came from: its service, when it was read, and its stated detail."""

    service_id: str
    publisher: str
    attribution: str
    retrieved_at: AwareDatetime
    # The publisher's stated scale or cell and edition; each None when not stated.
    detail: LayerDetail
    # The ground resolution the model assumes for it; None when the publisher states none.
    resolution_m: float | None = Field(gt=0)


class InputValue(DomainModel):
    """An input's value at a cell: a number with its unit, a category with its label, or
    ``absent`` (the input has no feature there, such as outside every groundwater body)."""

    number: float | None = None
    unit: str | None = None
    # A distance reported as "at least": nothing was found within the build's buffer.
    at_least: bool = False
    category: str | None = None
    label: str | None = None
    absent: bool = False

    @model_validator(mode="after")
    def _one_kind(self) -> Self:
        kinds = [self.number is not None, self.category is not None, self.absent]
        if sum(kinds) != 1:
            raise ValueError("a value is a number, a category or absent: exactly one")
        if (self.number is None) and (self.unit is not None or self.at_least):
            raise ValueError("only a number has a unit or an 'at least'")
        if self.number is not None and not math.isfinite(self.number):
            raise ValueError("a number must be finite")
        return self


class Contribution(DomainModel):
    criterion: str
    # The configured weight, and its share once renormalised over the inputs present.
    weight: float = Field(gt=0, le=1)
    share: float = _UNIT
    value: InputValue
    suitability: float = _UNIT
    contribution: float = _UNIT
    source: InputSource

    @model_validator(mode="after")
    def _product(self) -> Self:
        if abs(self.contribution - self.share * self.suitability) > _TOLERANCE:
            raise ValueError(f"{self.criterion}: contribution must be share x suitability")
        return self


class MissingReason(StrEnum):
    # No input exists for the criterion at this scale (nationwide, or around the parcel).
    NO_DATASET = "no_dataset"
    # The input has no value at this cell.
    NO_DATA = "no_data"


class MissingInput(DomainModel):
    criterion: str
    weight: float = Field(gt=0, le=1)
    reason: MissingReason


class ComponentId(StrEnum):
    COVERAGE = "coverage"
    RESOLUTION = "resolution"
    AGE = "age"
    EVIDENCE = "evidence"
    SKILL = "skill"


class ConfidenceLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfidenceComponent(DomainModel):
    id: ComponentId
    weight: float = _UNIT
    value: float = _UNIT
    # False for a component nothing has measured yet (the model's skill before session 07).
    measured: bool


class Confidence(DomainModel):
    value: float = _UNIT
    label: ConfidenceLabel
    components: tuple[ConfidenceComponent, ...]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        ids = [component.id for component in self.components]
        if sorted(ids) != sorted(ComponentId):
            raise ValueError("confidence has each of its components exactly once")
        if abs(sum(c.weight for c in self.components) - 1) > _TOLERANCE:
            raise ValueError("the confidence components' weights must add up to 1")
        if abs(self.value - sum(c.weight * c.value for c in self.components)) > _TOLERANCE:
            raise ValueError("confidence must be the weighted sum of its components")
        return self


class PotentialEstimate(DomainModel):
    """The score at a cell with everything that explains it."""

    # A relative potential index until session 07 calibrates the model: never a probability.
    kind: Literal["index"] = "index"
    # None when no input is present at the cell: there is no estimate there.
    score: float | None = _UNIT
    confidence: Confidence
    contributions: tuple[Contribution, ...]
    missing: tuple[MissingInput, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        names = [c.criterion for c in self.contributions] + [m.criterion for m in self.missing]
        if len(set(names)) != len(names):
            raise ValueError("each criterion is either present or missing, once")
        if not names:
            raise ValueError("an estimate names its criteria")
        if (self.score is None) != (not self.contributions):
            raise ValueError("there is a score exactly when some input is present")
        if self.score is not None:
            if abs(sum(c.share for c in self.contributions) - 1) > _TOLERANCE:
                raise ValueError("the shares of the inputs present must add up to 1")
            if abs(self.score - sum(c.contribution for c in self.contributions)) > _TOLERANCE:
                raise ValueError("the score must be the sum of the contributions")
        return self


class CellExplanation(DomainModel):
    """``GET /api/national/explain``: the national grid's estimate at a tapped point."""

    longitude: float
    latitude: float
    grid: str
    region_id: str
    region_name: str
    cell_m: float = Field(gt=0)
    built_at: AwareDatetime
    estimate: PotentialEstimate


class NationalFailure(StrEnum):
    NOT_BUILT = "not_built"
    OUTSIDE_BUILT_AREA = "outside_built_area"
    UNKNOWN_LAYER = "unknown_layer"
    INVALID_TILE = "invalid_tile"
    # A region's files cannot be read (written by an older version, or damaged).
    UNREADABLE = "unreadable"


class NationalError(Exception):
    def __init__(self, failure: NationalFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
