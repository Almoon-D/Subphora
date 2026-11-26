# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/section.yaml``: the interpretive geological cross-section
(MASTER_PLAN §4.4).

Whether the lithology's service is catalogued and its ageing profile defined is checked
against the other sections by ``Settings``.
"""

from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section
from subphora.domain.layers import LayerDetail

_REST_QUERY = r"^/.+/MapServer/\d+/query$"
_UNIT = Field(ge=0, le=1)


class LithologyDataset(Section):
    service: str
    path: str = Field(pattern=_REST_QUERY)
    label_field: str = Field(min_length=1)
    page_size: PositiveInt
    window_m: float = Field(ge=0)
    detail: LayerDetail
    ageing: str = Field(min_length=1)


class BoreholeSettings(Section):
    depth_field: str = Field(min_length=1)
    ground_field: str = Field(min_length=1)
    max_distance_m: PositiveFloat
    max_count: PositiveInt


class SectionConfidence(Section):
    map_only: float = _UNIT
    evidence_range_m: PositiveFloat
    depth_range_m: PositiveFloat
    fault_zone_m: float = Field(ge=0)
    fault_factor: float = _UNIT
    map_reach_m: float = Field(ge=0)
    dip_reach_m: float = Field(ge=0)


class SectionSettings(Section):
    min_length_m: PositiveFloat
    max_length_m: PositiveFloat
    sample_m: PositiveFloat
    column_m: PositiveFloat
    row_m: PositiveFloat
    depth_m: PositiveFloat
    lithology: LithologyDataset
    bedding_direction_field: str = Field(min_length=1)
    dip_max_distance_m: PositiveFloat
    boreholes: BoreholeSettings
    water_table_every_m: PositiveFloat
    confidence: SectionConfidence

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.min_length_m >= self.max_length_m:
            raise ValueError("min_length_m must be below max_length_m")
        if not self.sample_m <= self.column_m <= self.min_length_m:
            raise ValueError("sample_m <= column_m <= min_length_m: a line has columns")
        if self.row_m > self.depth_m:
            raise ValueError("row_m must not exceed depth_m")
        if self.confidence.map_reach_m > self.confidence.dip_reach_m:
            raise ValueError("a bedding measurement reaches at least as deep as the map alone")
        return self
