# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The estimated depth to water at a candidate spot and the drilling cost it implies
(MASTER_PLAN §4.3, depth and cost).

The water table comes only from piezometers of the groundwater body under the spot, with an
uncertainty that grows with distance; the owner's wells read at rest join them as private
levels of their own body when asked, never written into the public data. Beyond the
maximum distance, outside every body, or without any levels, the depth is "unknown" and
says why. A spot in carbonate rock
(possible karst) is flagged: there the water table between piezometers is unreliable. The
cost is a range in euros (``Decimal``), from priced settings that name their source.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel


class DepthUnknown(StrEnum):
    # No piezometric levels have been imported (``subphora piezometry import``).
    NOT_IMPORTED = "not_imported"
    # The spot lies in no groundwater body: no water table is drawn there.
    OUTSIDE_BODIES = "outside_bodies"
    # No piezometer of the spot's body lies within the maximum distance.
    NO_PIEZOMETER_NEARBY = "no_piezometer_nearby"
    # The terrain model has no elevation at the spot.
    NO_GROUND_ELEVATION = "no_ground_elevation"


class LevelsSource(DomainModel):
    """The piezometric levels used: their dataset, period and when they were imported."""

    service_id: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    # sha256 of the file imported, to tell one download from another.
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    imported_at: AwareDatetime
    levels_from: date
    levels_to: date

    @model_validator(mode="after")
    def _period(self) -> Self:
        if self.levels_to < self.levels_from:
            raise ValueError("the levels' period ends after it starts")
        return self


class OwnLevel(DomainModel):
    """One of the owner's wells as a private level: the water-table elevation its readings at
    rest give (m above sea level; ground from the area's terrain model, minus the depth
    below the ground), their range, how many and when, and its distance to the spot."""

    well_id: str = Field(min_length=1)
    distance_m: float = Field(ge=0)
    ground_m: float
    level_m: float
    low_m: float
    high_m: float
    readings: int = Field(ge=1)
    first: date
    last: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.low_m <= self.level_m <= self.high_m:
            raise ValueError("a level lies inside its range")
        if self.last < self.first:
            raise ValueError("the readings' period ends after it starts")
        return self


class WaterTable(DomainModel):
    """The interpolated water-table elevation (m above sea level) and its range."""

    elevation_m: float
    low_m: float
    high_m: float
    body: str = Field(min_length=1)
    body_label: str = Field(min_length=1)
    piezometers: int = Field(ge=1)
    nearest_m: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.low_m <= self.elevation_m <= self.high_m:
            raise ValueError("the water table lies inside its range")
        return self


class DepthEstimate(DomainModel):
    state: Literal["estimated", "unknown"]
    reason: DepthUnknown | None = None
    ground_m: float | None = None
    water_table: WaterTable | None = None
    # Metres below ground; never negative (a water table above ground reads as 0).
    depth_m: float | None = Field(default=None, ge=0)
    low_m: float | None = Field(default=None, ge=0)
    high_m: float | None = Field(default=None, ge=0)
    # Carbonate rock under the spot (possible karst): the depth is unreliable.
    karst: bool = False
    # The sources of the piezometers' levels used, national first.
    sources: tuple[LevelsSource, ...] = ()
    # The owner's wells used as private levels, nearest first.
    own_levels: tuple[OwnLevel, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        figures = (self.water_table, self.depth_m, self.low_m, self.high_m)
        if self.state == "estimated":
            if (
                self.reason is not None
                or not (self.sources or self.own_levels)
                or self.ground_m is None
                or self.water_table is None
                or self.depth_m is None
                or self.low_m is None
                or self.high_m is None
            ):
                raise ValueError("an estimated depth has every figure and its source, no reason")
            if not self.low_m <= self.depth_m <= self.high_m:
                raise ValueError("the depth lies inside its range")
        elif (
            self.reason is None
            or any(f is not None for f in figures)
            or self.sources
            or self.own_levels
        ):
            raise ValueError("an unknown depth says why and has no figures")
        return self


class DrillingCost(DomainModel):
    """The cost range of drilling to the estimated depth (and below the water table)."""

    currency: Literal["EUR"] = "EUR"
    low: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    # The metres priced: the depth range plus the drilling below the water table.
    drilled_low_m: Decimal = Field(ge=0)
    drilled_high_m: Decimal = Field(ge=0)
    per_metre_low: Decimal = Field(ge=0)
    per_metre_high: Decimal = Field(ge=0)
    fixed_low: Decimal = Field(ge=0)
    fixed_high: Decimal = Field(ge=0)
    source: str = Field(min_length=1)
    priced_on: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        pairs = (
            (self.low, self.high),
            (self.drilled_low_m, self.drilled_high_m),
            (self.per_metre_low, self.per_metre_high),
            (self.fixed_low, self.fixed_high),
        )
        if any(low > high for low, high in pairs):
            raise ValueError("each low figure is at most its high one")
        return self
