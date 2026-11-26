# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/packs.yaml``: offline packs (MASTER_PLAN §4.7).

Whether every listed layer may be stored (its service's terms) is checked against the
source catalogue by ``Settings``.
"""

from typing import Self

from pydantic import Field, PositiveInt, model_validator

from subphora.config.base import Section

_ZOOM = Field(ge=0, le=24)


class PackZoom(Section):
    min: int = _ZOOM
    max: int = _ZOOM

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("packs.zoom: min is above max")
        return self


class PackBaseMap(Section):
    id: str = Field(min_length=1)
    # The estimated size of one tile, for the estimate shown before a download.
    tile_bytes: PositiveInt


class PackDownload(Section):
    concurrency: int = Field(ge=1, le=16)
    retries: int = Field(ge=0, le=5)
    # The progress is written down every this many files.
    progress_every: PositiveInt


class PacksSettings(Section):
    buffer_m: float = Field(ge=0)
    zoom: PackZoom
    max_bytes: PositiveInt
    base_maps: list[PackBaseMap] = Field(min_length=1)
    # National tile layers, stored as tiles and as the detailed map's images.
    layers: list[str] = Field(min_length=1)
    national_tile_bytes: PositiveInt
    parcel_image_bytes: PositiveInt
    download: PackDownload
    network_timeout_ms: PositiveInt

    @model_validator(mode="after")
    def _unique(self) -> Self:
        bases = [base.id for base in self.base_maps]
        if len(set(bases)) != len(bases) or len(set(self.layers)) != len(self.layers):
            raise ValueError("packs: a base map or a layer is listed twice")
        return self
