# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/parcel.yaml``: the detailed potential map of an area of
interest (MASTER_PLAN §4.3, parcel scale).

Whether each service is catalogued, each ageing profile and tile layer defined, and each
distance cap at least its lookup's last break is checked against the other sections by
``Settings``.
"""

from pathlib import Path
from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section
from subphora.config.national import TerrainCoverage
from subphora.domain.layers import LayerDetail

_REST_QUERY = r"^/.+/MapServer/\d+/query$"


class ParcelTerrain(Section):
    service: str
    model: str = Field(min_length=1)
    # Per national grid id.
    coverages: dict[str, TerrainCoverage] = Field(min_length=1)
    window_m: PositiveFloat
    overlap_m: float = Field(ge=0)
    detail: LayerDetail
    ageing: str = Field(min_length=1)


class FaultsDataset(Section):
    service: str
    path: str = Field(pattern=_REST_QUERY)
    type_field: str = Field(min_length=1)
    kinds: list[str] = Field(min_length=1)
    exclude: list[str]
    page_size: PositiveInt
    radius_m: PositiveFloat
    detail: LayerDetail
    ageing: str = Field(min_length=1)

    def is_fault(self, kind: str) -> bool:
        return kind not in self.exclude and any(kind.startswith(k) for k in self.kinds)


class BeddingDataset(Section):
    service: str
    path: str = Field(pattern=_REST_QUERY)
    kind_field: str = Field(min_length=1)
    dip_field: str = Field(min_length=1)
    kinds: list[str] = Field(min_length=1)
    page_size: PositiveInt
    max_distance_m: PositiveFloat
    detail: LayerDetail
    ageing: str = Field(min_length=1)


class CandidateSettings(Section):
    count: PositiveInt
    min_confidence: float = Field(ge=0, le=1)
    min_separation_m: float = Field(ge=0)


class JobSettings(Section):
    workers: PositiveInt
    poll_after_s: PositiveFloat
    # Relative to the repository root unless absolute.
    output_dir: Path

    def output_path(self, root: Path) -> Path:
        return self.output_dir if self.output_dir.is_absolute() else root / self.output_dir


class LegalSettings(Section):
    not_evaluated_source: str = Field(min_length=1)
    disclaimer: str = Field(min_length=1)


class ParcelSettings(Section):
    resolution_m: PositiveFloat
    point_radius_m: PositiveFloat
    buffer_m: PositiveFloat
    max_cells: PositiveInt
    terrain: ParcelTerrain
    faults: FaultsDataset
    bedding: BeddingDataset
    water_points_radius_m: PositiveFloat
    candidates: CandidateSettings
    layers: list[str] = Field(min_length=1)
    image_max_px: PositiveInt
    jobs: JobSettings
    legal: LegalSettings

    @model_validator(mode="after")
    def _reach(self) -> Self:
        if self.faults.radius_m > self.buffer_m:
            raise ValueError("faults.radius_m must not exceed buffer_m: the window holds it")
        if len(set(self.layers)) != len(self.layers):
            raise ValueError("parcel layers must be unique")
        return self
