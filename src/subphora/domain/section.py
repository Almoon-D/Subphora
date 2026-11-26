# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The interpretive geological cross-section along a drawn line (MASTER_PLAN §4.4).

Everything in it is an interpretation and says so (``label``). Along the line: the ground
profile, the mapped units at the surface, their contacts (each projected downward with the
apparent dip of the nearest bedding measurement, or marked as not projected, or as lying
on a fault), the faults crossed, the public boreholes near the line and the water table
where session 07 can estimate it. Below the ground, a grid of cells: each one either an
interpreted unit with its confidence and that confidence's parts, or "unknown" (below the
deepest evidence at its column), never a guess without a mark.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.depth import DepthUnknown, LevelsSource, WaterTable
from subphora.domain.parcels import Position
from subphora.domain.potential import ConfidenceLabel, InputSource

_UNIT = Field(ge=0, le=1)
_TOLERANCE = 1e-6


class SectionFailure(StrEnum):
    """Why a section is refused or failed. Each has its own status."""

    INVALID_LINE = "invalid_line"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    OUTSIDE_TERRITORY = "outside_territory"
    OUTSIDE_COVERAGE = "outside_coverage"
    UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"


class SectionError(Exception):
    def __init__(self, failure: SectionFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail


class SectionGap(StrEnum):
    """Evidence the section lacks, said explicitly rather than drawn over."""

    # The geological map has no unit along the line.
    NO_UNITS = "no_units"
    # No bedding measurement is near enough to project any contact.
    NO_BEDDING = "no_bedding"
    # No public borehole with a recorded depth lies near the line.
    NO_BOREHOLES = "no_boreholes"
    # The public inventory records each borehole's depth, not its lithological log.
    NO_BOREHOLE_LOGS = "no_borehole_logs"
    # The water table is unknown all along the line.
    NO_WATER_TABLE = "no_water_table"
    # The terrain model has no elevation somewhere along the line.
    GROUND_INCOMPLETE = "ground_incomplete"


class ProfilePoint(DomainModel):
    distance_m: float = Field(ge=0)
    # None where the terrain model has no value.
    ground_m: float | None


class SurfaceUnit(DomainModel):
    """A stretch of the line on one mapped unit (``label`` None: the map has none there)."""

    index: int = Field(ge=0)
    from_m: float = Field(ge=0)
    to_m: float = Field(ge=0)
    label: str | None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.to_m <= self.from_m:
            raise ValueError("a unit's stretch ends after it starts")
        return self


class BeddingMeasurement(DomainModel):
    """A MAGNA bedding measurement, placed against the line."""

    distance_m: float
    # Perpendicular distance from the line (positive: to its right, looking along it).
    offset_m: float
    dip_deg: float = Field(ge=0, le=90)
    # Clockwise from north, the way the bed dips; None when the sheet records none.
    direction_deg: float | None = Field(ge=0, le=360)
    kind: str = Field(min_length=1)


class ContactState(StrEnum):
    # Projected downward with the apparent dip of the nearest bedding measurement.
    PROJECTED = "projected"
    # No usable measurement near it: drawn vertical, its dip unknown.
    NOT_PROJECTED = "not_projected"
    # It lies on a fault the line crosses: drawn along the fault, whose dip is not mapped.
    AT_FAULT = "at_fault"


class Contact(DomainModel):
    """Where the line passes from one surface unit to the next."""

    distance_m: float = Field(ge=0)
    ground_m: float | None
    # The surface units on either side (SurfaceUnit.index).
    before: int = Field(ge=0)
    after: int = Field(ge=0)
    state: ContactState
    # Degrees, signed: positive where the contact deepens toward the line's end.
    apparent_dip_deg: float | None = Field(default=None, ge=-90, le=90)
    measurement: BeddingMeasurement | None = None
    # Plan distance from the contact to its measurement.
    measurement_m: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        projected = self.state is ContactState.PROJECTED
        figures = (self.apparent_dip_deg, self.measurement, self.measurement_m)
        if projected and any(f is None for f in figures):
            raise ValueError("a projected contact has its apparent dip and its measurement")
        if not projected and any(f is not None for f in figures):
            raise ValueError("a contact not projected has no dip")
        if self.after != self.before + 1:
            raise ValueError("a contact lies between consecutive units")
        return self


class FaultCrossing(DomainModel):
    distance_m: float = Field(ge=0)
    kind: str = Field(min_length=1)


class Borehole(DomainModel):
    """A public borehole near the line: how deep it went (no lithological log)."""

    distance_m: float
    offset_m: float
    kind: str = Field(min_length=1)
    depth_m: float = Field(gt=0)
    # The inventory's ground elevation, else the terrain's; None when neither has one.
    ground_m: float | None


class WaterTablePoint(DomainModel):
    distance_m: float = Field(ge=0)
    state: Literal["estimated", "unknown"]
    reason: DepthUnknown | None = None
    water_table: WaterTable | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.state == "estimated") != (self.water_table is not None):
            raise ValueError("an estimated water table has its figures")
        if (self.state == "unknown") != (self.reason is not None):
            raise ValueError("an unknown water table says why")
        return self


class EvidenceKind(StrEnum):
    BEDDING = "bedding"
    BOREHOLE = "borehole"


class SectionCell(DomainModel):
    """A row of a column: from ``top_m`` to ``top_m`` + the section's ``row_m`` below ground."""

    top_m: float = Field(ge=0)
    state: Literal["interpreted", "unknown"]
    # SurfaceUnit.index of the unit interpreted here.
    unit: int | None = Field(default=None, ge=0)
    # Falls from 1 at the ground to 0 at the depth range.
    depth_factor: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    label: ConfidenceLabel | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        figures = (self.unit, self.depth_factor, self.confidence, self.label)
        if self.state == "interpreted" and any(f is None for f in figures):
            raise ValueError("an interpreted cell has its unit and its confidence")
        if self.state == "unknown" and any(f is not None for f in figures):
            raise ValueError("an unknown cell has no unit and no confidence")
        return self


class SectionColumn(DomainModel):
    distance_m: float = Field(ge=0)
    ground_m: float | None
    # The nearest evidence (a bedding measurement or a borehole) and its plan distance.
    evidence: EvidenceKind | None
    evidence_m: float | None = Field(ge=0)
    evidence_factor: float = _UNIT
    # Within the fault zone of a fault crossed: the factor applied, else 1.
    fault_factor: float = _UNIT
    # How deep the evidence reaches below the ground here; below it, "unknown".
    reach_m: float = Field(ge=0)
    cells: tuple[SectionCell, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.evidence is None) != (self.evidence_m is None):
            raise ValueError("the nearest evidence has its distance")
        if self.ground_m is None and any(c.state == "interpreted" for c in self.cells):
            raise ValueError("a column without ground elevation is unknown")
        return self


class CrossSection(DomainModel):
    """``POST /api/section``: the interpretive section under a straight line."""

    label: Literal["interpretation"] = "interpretation"
    start: Position
    end: Position
    crs: str = Field(min_length=1)
    length_m: float = Field(gt=0)
    # Clockwise from grid north, from start to end.
    azimuth_deg: float = Field(ge=0, lt=360)
    built_at: AwareDatetime
    column_m: float = Field(gt=0)
    row_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    profile: tuple[ProfilePoint, ...] = Field(min_length=2)
    units: tuple[SurfaceUnit, ...]
    contacts: tuple[Contact, ...]
    faults: tuple[FaultCrossing, ...]
    bedding: tuple[BeddingMeasurement, ...]
    boreholes: tuple[Borehole, ...]
    water_table: tuple[WaterTablePoint, ...]
    columns: tuple[SectionColumn, ...] = Field(min_length=1)
    # Per dataset: terrain, lithology, bedding, faults, boreholes, groundwater_bodies.
    sources: dict[str, InputSource]
    # The sources of the piezometric levels behind the water table.
    levels: tuple[LevelsSource, ...]
    gaps: tuple[SectionGap, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        indices = [u.index for u in self.units]
        if indices != list(range(len(self.units))):
            raise ValueError("units are numbered along the line from 0")
        if len(self.contacts) != max(0, len(self.units) - 1):
            raise ValueError("one contact between each pair of consecutive units")
        known = set(indices)
        for column in self.columns:
            if any(c.unit is not None and c.unit not in known for c in column.cells):
                raise ValueError("a cell's unit is one of the section's units")
        if SectionGap.NO_BOREHOLE_LOGS not in self.gaps:
            raise ValueError("the missing borehole logs are always said")
        if abs(self.profile[-1].distance_m - self.length_m) > _TOLERANCE + 1e-3:
            raise ValueError("the profile runs the whole line")
        return self
