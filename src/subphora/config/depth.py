# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schemas of ``config/defaults/piezometry.yaml`` (the piezometric levels and the water
table) and ``config/defaults/drilling.yaml`` (the drilling cost), MASTER_PLAN §4.3."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section


class PiezometryTables(Section):
    piezometers: str = Field(min_length=1)
    levels: str = Field(min_length=1)


class PiezometryColumns(Section):
    id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    x: str = Field(min_length=1)
    y: str = Field(min_length=1)
    zone: str = Field(min_length=1)
    ground: str = Field(min_length=1)
    body: str = Field(min_length=1)
    body_label: str = Field(min_length=1)
    level_id: str = Field(min_length=1)
    date: str = Field(min_length=1)
    level: str = Field(min_length=1)


class LevelSummary(Section):
    recent_years: PositiveFloat
    min_measurements: PositiveInt
    max_age_years: PositiveFloat
    low_quantile: float = Field(gt=0, lt=0.5)
    high_quantile: float = Field(gt=0.5, lt=1)


class WaterTableSettings(Section):
    max_distance_m: PositiveFloat
    max_piezometers: PositiveInt
    power: PositiveFloat
    growth_m_per_km: float = Field(ge=0)


class PiezometrySettings(Section):
    service: str = Field(min_length=1)
    # Relative to the repository root unless absolute.
    input: Path
    output: Path
    mdb_export: str = Field(min_length=1)
    tables: PiezometryTables
    columns: PiezometryColumns
    zones: dict[str, str] = Field(min_length=1)
    summary: LevelSummary
    water_table: WaterTableSettings
    karst_labels: list[str]

    def input_path(self, root: Path) -> Path:
        return self.input if self.input.is_absolute() else root / self.input

    def output_path(self, root: Path) -> Path:
        return self.output if self.output.is_absolute() else root / self.output

    def is_karst(self, label: str) -> bool:
        upper = label.strip().upper()
        return any(upper.startswith(k.upper()) for k in self.karst_labels)


class CostRange(Section):
    low: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        return self


class DrillingSettings(Section):
    currency: Literal["EUR"]
    per_metre: CostRange
    fixed: CostRange
    below_water_table_m: float = Field(ge=0)
    source: str = Field(min_length=1)
    priced_on: date
