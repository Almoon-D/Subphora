# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The imported piezometric levels: one summary per piezometer of the national database
and the basin authorities' spreadsheets (MASTER_PLAN §4.3, depth), written by
``subphora piezometry import`` under ``data/``.

A piezometer's level is the median of its measurements over the recent window the import
settings name, with the 10th and 90th percentiles as its seasonal range, whichever source
measured them; it names the sources of the levels in that window. A piezometer without
enough recent measurements is left out, never filled in.
"""

from datetime import date
from typing import Self

from pydantic import Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.depth import LevelsSource


class Piezometer(DomainModel):
    # The national database's id, or "<service>:<code>" for one only a basin file holds.
    id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    name: str
    # The groundwater body it monitors (its EU code), and that body's name.
    body: str = Field(min_length=1)
    body_label: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    ground_m: float | None
    # Water-table elevation in metres above sea level.
    level_m: float
    level_low_m: float
    level_high_m: float
    measurements: int = Field(ge=1)
    first: date
    last: date
    # The services whose levels fall in the summarised window.
    sources: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.level_low_m <= self.level_m <= self.level_high_m:
            raise ValueError("a piezometer's level lies inside its range")
        if self.last < self.first:
            raise ValueError("a piezometer's last measurement follows its first")
        return self


class PiezometryDataset(DomainModel):
    # Each file imported, the national database first; only those some piezometer uses.
    sources: tuple[LevelsSource, ...] = Field(min_length=1)
    # Stations read, and those left out for too few recent measurements or no body.
    piezometers_read: int = Field(ge=0)
    levels_read: int = Field(ge=0)
    left_out: int = Field(ge=0)
    piezometers: tuple[Piezometer, ...]

    @model_validator(mode="after")
    def _sources_named(self) -> Self:
        ids = [s.service_id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("each source of levels is listed once")
        used = {s for p in self.piezometers for s in p.sources}
        if not used <= set(ids):
            raise ValueError(f"piezometers name unlisted sources: {sorted(used - set(ids))}")
        return self

    def source_map(self) -> dict[str, LevelsSource]:
        return {s.service_id: s for s in self.sources}
