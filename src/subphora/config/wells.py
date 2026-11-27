# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/wells.yaml``: the owner's well registry, its CSV import and
the update of the map from it (MASTER_PLAN §4.3 Learning, decision 0040)."""

from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, PositiveFloat, PositiveInt, field_validator, model_validator

from subphora.config.base import Section

# The CSV columns the import reads, each with the names that stand for it.
CSV_COLUMNS = frozenset(
    {
        "id",
        "name",
        "longitude",
        "latitude",
        "x",
        "y",
        "crs",
        "depth_m",
        "flow_l_s",
        "outcome",
        "drilled_on",
        "note",
        "measured_at",
        "depth_to_water_m",
    }
)


class WellsStoreSettings(Section):
    database: Path
    busy_timeout_s: PositiveFloat

    def database_path(self, root: Path) -> Path:
        return self.database if self.database.is_absolute() else root / self.database


class UpdateSettings(Section):
    prior_strength: PositiveFloat
    half_weight_m: PositiveFloat
    range_m: PositiveFloat
    prior_margin: float = Field(gt=0, lt=0.5)
    level: float = Field(gt=0, lt=1)
    layer_id: str = Field(pattern=r"^[a-z0-9-]+$")
    legend_layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def _range_beyond_half(self) -> Self:
        if self.range_m < self.half_weight_m:
            raise ValueError("wells.update.range_m is below half_weight_m")
        return self


class OutcomeWords(Section):
    productive: list[str] = Field(min_length=1)
    dry: list[str] = Field(min_length=1)
    unknown: list[str] = Field(min_length=1)


class CsvSettings(Section):
    max_bytes: PositiveInt
    max_rows: PositiveInt
    columns: dict[str, list[str]]
    outcomes: OutcomeWords
    productive_above_l_s: float = Field(ge=0)
    date_formats: list[str] = Field(min_length=1)
    datetime_formats: list[str] = Field(min_length=1)
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"wells.csv.timezone: {value!r} is not a time zone") from exc
        return value

    @model_validator(mode="after")
    def _every_column_named(self) -> Self:
        if set(self.columns) != CSV_COLUMNS:
            raise ValueError(f"wells.csv.columns names exactly {sorted(CSV_COLUMNS)}")
        if any(not names for names in self.columns.values()):
            raise ValueError("wells.csv.columns: every column has a name")
        words = [*self.outcomes.productive, *self.outcomes.dry, *self.outcomes.unknown]
        if len({w.lower() for w in words}) != len(words):
            raise ValueError("wells.csv.outcomes: a word stands for one outcome")
        return self


class OwnerValidationSettings(Section):
    labels_source: str = Field(min_length=1)


class WellsSettings(Section):
    store: WellsStoreSettings
    name_max_chars: PositiveInt
    note_max_chars: PositiveInt
    update: UpdateSettings
    csv: CsvSettings
    validation: OwnerValidationSettings
