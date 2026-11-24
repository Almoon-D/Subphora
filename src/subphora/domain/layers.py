# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What a tap on an official layer returns, and the ways a layer request can fail."""

from enum import StrEnum

from pydantic import Field

from subphora.domain import DomainModel
from subphora.domain.provenance import Provenance


class InfoField(DomainModel):
    # The field's name as the service gives it, and its value as text.
    name: str = Field(min_length=1)
    value: str


class InfoFeature(DomainModel):
    fields: tuple[InfoField, ...] = Field(min_length=1)


class LayerFeatureInfo(DomainModel):
    """The features of one layer under a tapped point: only the fields the catalogue allows.

    No features is an answer too: nothing of this layer at that point.
    """

    layer_id: str
    features: tuple[InfoFeature, ...]
    source: Provenance


class LayerFailure(StrEnum):
    """Why a tile or a tap could not be answered. Each maps to its own HTTP status."""

    UNKNOWN_LAYER = "unknown_layer"
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
