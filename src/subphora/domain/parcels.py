# Copyright (c) 2026 Almoon-D. All rights reserved.
"""A cadastral parcel as it crosses the API, and the ways a lookup can fail."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from subphora.domain import DomainModel

# GeoJSON positions are (longitude, latitude) in EPSG:4326 (RFC 7946).
type Position = tuple[float, float]
type Ring = tuple[Position, ...]
type Polygon = tuple[Ring, ...]


class ReferenceKind(StrEnum):
    URBAN = "urban"
    RUSTIC = "rustic"


class CadastralReference(DomainModel):
    """A validated parcel reference: the 14-character parcel part, and its kind.

    ``province_code`` is the two-digit province of a rustic reference; an urban reference
    does not carry its province.
    """

    parcel: str = Field(min_length=14, max_length=14)
    kind: ReferenceKind
    province_code: str | None = Field(default=None, min_length=2, max_length=2)


class MultiPolygon(DomainModel):
    """A GeoJSON MultiPolygon in EPSG:4326: outer ring first, then holes, per polygon."""

    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: tuple[Polygon, ...] = Field(min_length=1)


class LocalPoint(DomainModel):
    """A point in the projected CRS used for measurements at the parcel."""

    crs: str
    x: float
    y: float


class Provenance(DomainModel):
    """Where a piece of data came from and when it was fetched from its publisher."""

    service_id: str
    publisher: str
    attribution: str
    retrieved_at: AwareDatetime


class CadastralParcel(DomainModel):
    reference: str = Field(min_length=14, max_length=14)
    # The cadastral area of the parcel as Catastro records it, in square metres.
    area_m2: float = Field(gt=0)
    municipality: str
    province: str
    # ISO 3166-2 codes (decision 0014): the province (ES-C) and the region (ES-GA).
    province_code: str
    region_code: str
    geometry: MultiPolygon
    # West, south, east, north in EPSG:4326.
    bbox: tuple[float, float, float, float]
    # Catastro's reference point of the parcel, in EPSG:4326 and in the parcel's local CRS.
    reference_point: Position
    reference_point_local: LocalPoint
    sources: tuple[Provenance, ...] = Field(min_length=1)


class LookupFailure(StrEnum):
    """Why a parcel lookup failed. Each maps to its own HTTP status and message."""

    MALFORMED = "malformed_reference"
    NOT_SUPPORTED = "territory_not_supported"
    NOT_FOUND = "parcel_not_found"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_ERROR = "upstream_error"


class ParcelLookupError(Exception):
    """A lookup that cannot return a parcel; ``failure`` says why."""

    def __init__(self, failure: LookupFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
