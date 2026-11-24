# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What a tap on an official layer returns, and the ways a layer request can fail.

Every map theme has a national layer and, where a region, province or basin authority
publishes a more detailed official service that qualifies (decision 0023), regional ones.
A tap says which of them answered, at what scale and of what date, and why a regional
layer that covers the point did not.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.provenance import Provenance


class InfoField(DomainModel):
    # The field's name as the service gives it, and its value as text.
    name: str = Field(min_length=1)
    value: str


class InfoFeature(DomainModel):
    fields: tuple[InfoField, ...] = Field(min_length=1)


class LayerLevel(StrEnum):
    NATIONAL = "national"
    REGIONAL = "regional"


class LayerDetail(DomainModel):
    """How detailed and how recent a layer's data are, as its publisher states them.

    A map scale (1:25,000) or a grid cell (250 m), or neither when the publisher states
    none; the edition year, or none when it is not stated. Never guessed.
    """

    scale_denominator: int | None = Field(default=None, gt=0)
    cell_m: float | None = Field(default=None, gt=0)
    edition: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def _one_measure(self) -> Self:
        if self.scale_denominator is not None and self.cell_m is not None:
            raise ValueError("a layer has a map scale or a grid cell, not both")
        return self


class Answer(DomainModel):
    """The layer that answered a tap: national, or regional inside one of its areas."""

    level: LayerLevel
    layer_id: str
    publisher: str
    detail: LayerDetail
    # The area (ISO 3166-2 region or river-basin district) of a regional answer.
    area_id: str | None = None

    @model_validator(mode="after")
    def _area_of_regional(self) -> Self:
        if (self.level is LayerLevel.REGIONAL) != (self.area_id is not None):
            raise ValueError("an area is named exactly when a regional layer answered")
        return self


class FallbackReason(StrEnum):
    """Why a regional layer covering the point did not give the answer."""

    # It answered, but has nothing at that point.
    NO_FEATURE = "no_feature"
    UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    # Its area's official boundary could not be read, so the point could not be placed.
    BOUNDARY_UNAVAILABLE = "boundary_unavailable"


class Fallback(DomainModel):
    layer_id: str
    reason: FallbackReason


class LayerFeatureInfo(DomainModel):
    """The features of one map theme under a tapped point: only the fields the catalogue
    allows, from the layer that answered.

    No features is an answer too: nothing of this theme at that point.
    """

    # The theme (the panel's entry); ``answered_by`` names the layer that answered.
    layer_id: str
    features: tuple[InfoFeature, ...]
    source: Provenance
    answered_by: Answer
    # The regional layers asked before the answer, in order, and why each gave none.
    fallbacks: tuple[Fallback, ...] = ()


class LayerFailure(StrEnum):
    """Why a tile or a tap could not be answered. Each maps to its own HTTP status."""

    UNKNOWN_LAYER = "unknown_layer"
    UNKNOWN_AREA = "unknown_area"
    # The layer is drawn by the browser from its service: the API does not relay it.
    NOT_PROXIED = "not_proxied"
    NO_FEATURE_INFO = "no_feature_info"
    INVALID_TILE = "invalid_tile"
    OUTSIDE_ZOOM_RANGE = "outside_zoom_range"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_ERROR = "upstream_error"


class LayerError(Exception):
    def __init__(self, failure: LayerFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
