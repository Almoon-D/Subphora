# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/report.yaml``: the PDF report and export pack (§4.6).

That every layer is one the detailed map draws is checked by ``Settings``."""

import re
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, PositiveInt, model_validator

from subphora.config.base import Section

_COLOUR = r"^#[0-9a-fA-F]{6}$"


class PackSettings(Section):
    cog_blocksize: int = Field(ge=16, le=4096, multiple_of=16)
    cog_compress: Literal["deflate", "lzw", "zstd"]


class ReportSettings(Section):
    catalogue: Path
    time_zone: str
    time_zones: dict[str, str] = Field(default_factory=dict)
    layers: list[str] = Field(min_length=1)
    map_max_px: PositiveInt
    map_width_mm: float = Field(gt=0, le=200)
    outline_colour: str = Field(pattern=_COLOUR)
    candidate_colour: str = Field(pattern=_COLOUR)
    pack: PackSettings

    @model_validator(mode="after")
    def _zones_exist(self) -> Self:
        for crs, zone in {"default": self.time_zone, **self.time_zones}.items():
            try:
                ZoneInfo(zone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(f"report.time_zones: {crs}: {zone!r} is not a time zone") from exc
            if crs != "default" and not re.fullmatch(r"EPSG:\d+", crs):
                raise ValueError(f"report.time_zones: {crs!r} is not an EPSG code")
        if len(set(self.layers)) != len(self.layers):
            raise ValueError("report.layers: a layer is listed twice")
        return self

    def catalogue_path(self, root: Path) -> Path:
        return self.catalogue if self.catalogue.is_absolute() else root / self.catalogue

    def zone(self, crs: str) -> ZoneInfo:
        return ZoneInfo(self.time_zones.get(crs, self.time_zone))
