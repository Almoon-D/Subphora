# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The area of interest: the place the rest of the app analyses, whatever found it.

A search (a cadastral or SIGPAC reference, an address, a municipality, coordinates) or a
drawing on the map ends in one ``AreaOfInterest``: a point or a multipolygon in EPSG:4326,
where it is (province, region, the CRS for measurements there) and what named it.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.parcels import CadastralParcel, LocalPoint, MultiPolygon, Position
from subphora.domain.provenance import Provenance


class AoiOrigin(StrEnum):
    """What the area came from; the front end names it."""

    CADASTRAL = "cadastral"
    SIGPAC_ENCLOSURE = "sigpac_enclosure"
    SIGPAC_PARCEL = "sigpac_parcel"
    MUNICIPALITY = "municipality"
    # A town or village (CartoCiudad's "población").
    PLACE = "place"
    STREET = "street"
    ADDRESS = "address"
    COORDINATES = "coordinates"
    DRAWN_POINT = "drawn_point"
    DRAWN_POLYGON = "drawn_polygon"


# The origins whose area is a point; every other one is an outline.
POINT_ORIGINS = frozenset(
    {AoiOrigin.COORDINATES, AoiOrigin.DRAWN_POINT, AoiOrigin.ADDRESS, AoiOrigin.STREET}
)


class PointGeometry(DomainModel):
    """A GeoJSON Point in EPSG:4326."""

    type: Literal["Point"] = "Point"
    coordinates: Position


class AreaOfInterest(DomainModel):
    origin: AoiOrigin
    # How the source names it: a reference, an address, typed coordinates; None for a
    # drawn polygon, which has no name.
    label: str | None = Field(min_length=1)
    geometry: Annotated[PointGeometry | MultiPolygon, Field(discriminator="type")]
    # West, south, east, north in EPSG:4326.
    bbox: tuple[float, float, float, float]
    # A point of the area: the point itself, the parcel's reference point, the place's
    # centre as CartoCiudad gives it, or a point inside the polygon. Also in the local CRS.
    centre: Position
    centre_local: LocalPoint
    # In square metres: the publisher's own figure (Catastro, SIGPAC) or the geodesic area
    # of the outline; None for a point.
    area_m2: float | None = Field(gt=0)
    # The municipality's name where the source gives it.
    municipality: str | None
    province: str
    # ISO 3166-2 codes (decision 0014).
    province_code: str
    region_code: str
    # False only in a territory SIGPAC does not cover (Ceuta, Melilla), where the
    # territory's box alone placed a typed or drawn point on land.
    land_checked: bool
    sources: tuple[Provenance, ...]
    # The cadastral parcel, for an area found by its cadastral reference.
    parcel: CadastralParcel | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        is_point = isinstance(self.geometry, PointGeometry)
        if is_point != (self.area_m2 is None):
            raise ValueError("a point has no area and an outline has one")
        if is_point != (self.origin in POINT_ORIGINS):
            raise ValueError(f"an area from {self.origin} has the wrong geometry")
        if (self.parcel is not None) != (self.origin == AoiOrigin.CADASTRAL):
            raise ValueError("only an area found by its cadastral reference has a parcel")
        if self.label is None and self.origin != AoiOrigin.DRAWN_POLYGON:
            raise ValueError("only a drawn polygon has no label")
        if not self.sources and self.land_checked:
            raise ValueError("an area checked on land names the source that checked it")
        return self


class SearchKind(StrEnum):
    CADASTRAL = "cadastral"
    SIGPAC = "sigpac"
    COORDINATES = "coordinates"
    PLACE = "place"


class Interpretation(DomainModel):
    """One way to read what was typed; the front end asks ``resolve`` for the area."""

    kind: SearchKind
    origin: AoiOrigin
    # The reference, the address or the coordinates as read.
    label: str = Field(min_length=1)
    # Where a place candidate is (municipality, province), or the CRS coordinates are in.
    detail: str | None
    # For coordinates: the point they give, in EPSG:4326.
    position: Position | None
    # The API path that returns the AreaOfInterest.
    resolve: str = Field(pattern=r"^/api/aoi/")


class SearchAnswer(DomainModel):
    # One reading is resolved at once; several are offered as an explicit choice.
    interpretations: tuple[Interpretation, ...] = Field(min_length=1)


class SearchFailure(StrEnum):
    """Why a search or a drawn area gives no area. Each maps to its own HTTP status."""

    EMPTY = "empty_query"
    MALFORMED_REFERENCE = "malformed_reference"
    MALFORMED_SIGPAC = "malformed_sigpac"
    MALFORMED_COORDINATES = "malformed_coordinates"
    WRONG_UTM_ZONE = "wrong_utm_zone"
    OUTSIDE_COUNTRY = "outside_country"
    INVALID_POLYGON = "invalid_polygon"
    TERRITORY_NOT_SUPPORTED = "territory_not_supported"
    NOT_FOUND = "not_found"
    NO_MATCH = "no_match"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_ERROR = "upstream_error"


class SearchError(Exception):
    """A search that ends without an area; ``source`` names the service that failed or
    found nothing, when one did."""

    def __init__(self, failure: SearchFailure, detail: str, source: str | None = None) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
        self.source = source
