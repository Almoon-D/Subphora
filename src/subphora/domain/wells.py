# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The owner's well registry and what the map learns from it (MASTER_PLAN §4.3 Learning,
§3 Privacy; decision 0040).

A well has an id (a UUID made where it was first recorded), the owner's name for it, its
position in degrees, what is known of it (depth, flow, the date it was drilled, a note)
and its outcome: productive, dry or unknown. Its water-level readings are typed by hand
(decision 0042: no instrument): a dated depth to the water below a stated reference (the
ground, or the top of the casing at a stated height above it), who measured it, and
whether the pump was stopped or running, and for how long, since a pumping well reads low.
The registry is private data: it lives only in ``data/``.

The update of the map at a cell is a Beta-Bernoulli update of the map's own value there,
each known well weighing by its distance; a ``WellUpdate`` carries the value before and
after, its interval, and every well that moved it, so that no updated number crosses the
API without what made it.
"""

import math
import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from subphora.domain import DomainModel
from subphora.domain.depth import DepthEstimate
from subphora.domain.validation import DomainValidation, LabelDesign

_UNIT = Field(ge=0, le=1)
# The update's value before and after is the same, within this, where no well weighs.
_TOLERANCE = 1e-9


def canonical_uuid(value: str) -> str:
    """The id in its canonical form, or an error unless it is a UUID."""
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("not a UUID") from exc
    canonical = str(parsed)
    if canonical != value:
        raise ValueError("a UUID is written in lower case with hyphens")
    return canonical


class WellOutcome(StrEnum):
    PRODUCTIVE = "productive"
    DRY = "dry"
    # Not drilled yet, not tested, or not recorded: no evidence either way.
    UNKNOWN = "unknown"


# The outcomes that are evidence.
KNOWN_OUTCOMES = frozenset({WellOutcome.PRODUCTIVE, WellOutcome.DRY})


class Well(DomainModel):
    id: str
    name: str = Field(min_length=1)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    # The depth drilled or dug, in metres.
    depth_m: float | None = Field(default=None, ge=0)
    # The flow it gives, in litres per second.
    flow_l_s: float | None = Field(default=None, ge=0)
    outcome: WellOutcome
    drilled_on: date | None = None
    note: str | None = None

    @field_validator("id")
    @classmethod
    def _uuid(cls, value: str) -> str:
        return canonical_uuid(value)

    @field_validator("name", "note")
    @classmethod
    def _stripped(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("no leading or trailing spaces")
        return value


class LevelReference(StrEnum):
    """What a reading's depth is measured from."""

    GROUND = "ground"
    CASING_TOP = "casing_top"


class MeasuredBy(StrEnum):
    OWNER = "owner"
    DRILLER = "driller"
    CONTRACTOR = "contractor"
    # Not recorded (an imported reading that does not say).
    UNKNOWN = "unknown"


class PumpState(StrEnum):
    """The well's pump when the level was read: a running pump draws the level down, and a
    pump stopped a short while ago leaves it still recovering."""

    STOPPED = "stopped"
    RUNNING = "running"
    UNKNOWN = "unknown"


class WellReading(DomainModel):
    """A water level read in a well: the depth to the water below ``reference`` (negative
    where the water rises above it), the reference's height above the ground, who read it,
    and the pump's state for ``pump_minutes`` before (None: not stated). A reading that does
    not state them (one imported, or kept before they were asked) is from the ground, by
    someone unknown, with the pump's state unknown."""

    id: str
    well_id: str
    measured_at: AwareDatetime
    depth_to_water_m: float
    reference: LevelReference = LevelReference.GROUND
    reference_height_m: float = Field(default=0.0, ge=0)
    measured_by: MeasuredBy = MeasuredBy.UNKNOWN
    pump: PumpState = PumpState.UNKNOWN
    pump_minutes: int | None = Field(default=None, ge=0)

    @field_validator("id", "well_id")
    @classmethod
    def _uuid(cls, value: str) -> str:
        return canonical_uuid(value)

    @model_validator(mode="after")
    def _stated(self) -> Self:
        if not math.isfinite(self.reference_height_m):
            raise ValueError("a height is a finite number")
        if self.reference is LevelReference.GROUND and self.reference_height_m != 0:
            raise ValueError("the ground stands at no height above itself")
        if self.pump is PumpState.UNKNOWN and self.pump_minutes is not None:
            raise ValueError("a pump in an unknown state has no duration")
        return self

    @property
    def below_ground_m(self) -> float:
        """The depth to the water below the ground."""
        return self.depth_to_water_m - self.reference_height_m

    @field_validator("measured_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("depth_to_water_m")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("a level is a finite number")
        return value


class WellRecord(DomainModel):
    """A well with its readings, oldest first."""

    well: Well
    readings: tuple[WellReading, ...]

    @model_validator(mode="after")
    def _own_readings(self) -> Self:
        if any(r.well_id != self.well.id for r in self.readings):
            raise ValueError("a well's readings are its own")
        times = [r.measured_at for r in self.readings]
        if times != sorted(times):
            raise ValueError("readings are oldest first")
        return self


class Registry(DomainModel):
    """``GET /api/wells``: every well, by name; and a stamp that changes whenever the
    wells that update the map change."""

    wells: tuple[WellRecord, ...]
    stamp: str = Field(pattern=r"^[0-9a-f]{16}$")


class Change(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    # A reading under an id already held with other content: the first is kept.
    CONFLICT = "conflict"


class WellSaved(DomainModel):
    id: str
    change: Change


class ReadingBatch(DomainModel):
    """``POST /api/wells/readings``: readings sent from the device's outbox."""

    readings: tuple[WellReading, ...] = Field(min_length=1)


class ReadingOutcome(StrEnum):
    CREATED = "created"
    # The same id with the same content: a retried sync.
    DUPLICATE = "duplicate"
    # The same id with other content: the first copy stays.
    CONFLICT = "conflict"
    # The well was deleted (or never stored): nothing is kept.
    UNKNOWN_WELL = "unknown_well"


class ReadingResult(DomainModel):
    id: str
    outcome: ReadingOutcome


class ReadingBatchAnswer(DomainModel):
    results: tuple[ReadingResult, ...]


class ImportReport(DomainModel):
    """What a CSV import did: wells and readings by what happened to them. Rows that
    disagree with what is held are conflicts, listed by row; nothing is overwritten."""

    rows: int = Field(ge=0)
    wells: dict[Change, int]
    readings: dict[Change, int]
    conflict_rows: tuple[int, ...]


class WellsFailure(StrEnum):
    INVALID_WELL = "invalid_well"
    INVALID_CSV = "invalid_csv"
    TOO_LARGE = "too_large"
    UNKNOWN_WELL = "unknown_well"
    CONFLICT = "conflict"
    STORE_UNAVAILABLE = "store_unavailable"


class WellsError(Exception):
    """A refused registry request. The detail says where, never what a record holds."""

    def __init__(self, failure: WellsFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail


class WellEvidence(DomainModel):
    """A known well that moved the value at a point, and by how much it weighs there."""

    well_id: str
    outcome: Literal[WellOutcome.PRODUCTIVE, WellOutcome.DRY]
    distance_m: float = Field(ge=0)
    weight: float = Field(gt=0, le=1)


class WellUpdate(DomainModel):
    """The map's value at a point updated with the owner's wells (decision 0040).

    ``kind`` is that of the value updated: a probability only where the cell's domain is
    calibrated; otherwise the index, and the updated value is an index too, never a
    probability. The interval is the Beta posterior's, at ``level``."""

    kind: Literal["index", "probability"]
    prior: float = _UNIT
    value: float = _UNIT
    low: float = _UNIT
    high: float = _UNIT
    level: float = Field(gt=0, lt=1)
    # How many wells of evidence the map's own value counts as.
    prior_strength: float = Field(gt=0)
    half_weight_m: float = Field(gt=0)
    range_m: float = Field(gt=0)
    evidence: tuple[WellEvidence, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.low <= self.value <= self.high:
            raise ValueError("an updated value lies inside its interval")
        if any(e.distance_m > self.range_m for e in self.evidence):
            raise ValueError("no well beyond the range weighs")
        if not self.evidence and abs(self.value - self.prior) > _TOLERANCE:
            raise ValueError("without evidence the value is the map's own")
        return self


class LevelLeftOut(StrEnum):
    """Why a reading does not enter the depth to water as a private level."""

    # The pump was running: the level is drawn down.
    PUMPING = "pumping"
    # The pump's state is not known: it may have been running.
    PUMP_UNKNOWN = "pump_unknown"
    # The pump had stopped less than the settings' rest time before: still recovering.
    RECOVERING = "recovering"
    # The well's readings at rest are too old or too few for a level.
    TOO_OLD = "too_old"
    # The well lies outside the detailed map's grid: its ground and body are not known.
    OUTSIDE_AREA = "outside_area"
    # The terrain model has no elevation at the well.
    NO_GROUND_ELEVATION = "no_ground_elevation"
    # The well lies in no groundwater body.
    OUTSIDE_BODIES = "outside_bodies"


class DepthWithWells(DomainModel):
    """The depth to water at a tapped point: from the public piezometry alone, and with the
    owner's wells read at rest as private levels of their own body (computed when asked;
    the area's stored map and its candidates keep the public one). ``left_out`` counts the
    owner's readings that did not enter, by why."""

    public: DepthEstimate
    with_wells: DepthEstimate
    left_out: dict[LevelLeftOut, int]

    @model_validator(mode="after")
    def _apart(self) -> Self:
        if self.public.own_levels:
            raise ValueError("the public depth holds no private level")
        if any(n <= 0 for n in self.left_out.values()):
            raise ValueError("a reason counts at least one reading")
        return self


class OwnerValidation(DomainModel):
    """``GET /api/wells/validation``: the index against the owner's wells, per domain of
    the national map, apart from the public wells' validation (decision 0030's method)."""

    validations: tuple[DomainValidation, ...]
    # Known wells no national map holds, and wells whose outcome is unknown: neither is
    # a label.
    off_map: int = Field(ge=0)
    unknown_outcome: int = Field(ge=0)

    @model_validator(mode="after")
    def _presence_absence(self) -> Self:
        if any(v.design not in {None, LabelDesign.PRESENCE_ABSENCE} for v in self.validations):
            raise ValueError("the owner's wells are productive against dry, never background")
        domains = [v.domain for v in self.validations]
        if len(set(domains)) != len(domains):
            raise ValueError("each domain is validated once")
        return self


__all__ = [
    "KNOWN_OUTCOMES",
    "Change",
    "DepthWithWells",
    "ImportReport",
    "LevelLeftOut",
    "LevelReference",
    "MeasuredBy",
    "OwnerValidation",
    "PumpState",
    "ReadingBatch",
    "ReadingBatchAnswer",
    "ReadingOutcome",
    "ReadingResult",
    "Registry",
    "Well",
    "WellEvidence",
    "WellOutcome",
    "WellReading",
    "WellRecord",
    "WellSaved",
    "WellUpdate",
    "WellsError",
    "WellsFailure",
    "canonical_uuid",
]
