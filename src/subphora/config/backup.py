# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/backup.yaml``: backups of data/ (MASTER_PLAN §4.9)."""

from datetime import time
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, PositiveInt, field_validator, model_validator

from subphora.config.base import Section


class NightlySettings(Section):
    at: time
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"backup.nightly.timezone: {value!r} is not a time zone") from exc
        return value

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class BackupSettings(Section):
    # Relative to the repository root unless absolute.
    source: Path
    destination: Path
    exclude: tuple[str, ...] = Field(default=())
    keep: PositiveInt
    nightly: NightlySettings

    @model_validator(mode="after")
    def _plain_folder_names(self) -> Self:
        for name in self.exclude:
            if not name or "/" in name or "\\" in name or name in (".", ".."):
                raise ValueError(f"backup.exclude: {name!r} is not a top-level folder name")
        return self

    def source_path(self, root: Path) -> Path:
        return self.source if self.source.is_absolute() else root / self.source

    def destination_path(self, root: Path) -> Path:
        return self.destination if self.destination.is_absolute() else root / self.destination
