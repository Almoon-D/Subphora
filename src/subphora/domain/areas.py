# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The official boundary of an area, inside which a regional layer is drawn and asked."""

from enum import StrEnum

from pydantic import Field

from subphora.domain import DomainModel
from subphora.domain.parcels import MultiPolygon
from subphora.domain.provenance import Provenance


class AreaKind(StrEnum):
    # An autonomous community or city (ISO 3166-2: ES-NC).
    REGION = "region"
    # A river-basin district (ES060), for a basin authority's layers.
    DISTRICT = "district"


class AreaBoundary(DomainModel):
    """The area's boundary in EPSG:4326, rounded to the configured grid."""

    id: str
    kind: AreaKind
    # West, south, east, north.
    bbox: tuple[float, float, float, float]
    geometry: MultiPolygon
    source: Provenance
    # The rounding grid in degrees: every area uses the same one, so borders stay shared.
    grid_deg: float = Field(gt=0)
