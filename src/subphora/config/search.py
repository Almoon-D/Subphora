# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/search.yaml``: territories, SIGPAC, CartoCiudad, drawing."""

from typing import Literal, Self

from pydantic import Field, model_validator

from subphora.config.base import Section

type Box = tuple[float, float, float, float]
# The kinds of area a CartoCiudad candidate can become (subphora.domain.aoi.AoiOrigin).
type PlaceOrigin = Literal["municipality", "place", "street", "address"]


class Territory(Section):
    id: str = Field(min_length=1)
    # West, south, east, north in degrees.
    bbox: Box
    utm_zones: tuple[int, ...] = Field(min_length=1)
    land_check: bool
    # The two-digit province code, for a territory the land check does not cover.
    province: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        west, south, east, north = self.bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(f"territory {self.id}: bbox is not west, south, east, north")
        if not self.land_check and self.province is None:
            raise ValueError(f"territory {self.id}: without the land check it needs a province")
        if self.land_check and self.province is not None:
            raise ValueError(f"territory {self.id}: the land check names the province")
        return self


class SigpacSearch(Section):
    service: str


class CartoCiudadSearch(Section):
    service: str
    max_candidates: int = Field(ge=1, le=50)
    types: dict[str, PlaceOrigin] = Field(min_length=1)


class DrawnPolygon(Section):
    max_vertices: int = Field(ge=3)


class SearchSettings(Section):
    territories: tuple[Territory, ...] = Field(min_length=1)
    sigpac: SigpacSearch
    cartociudad: CartoCiudadSearch
    drawn_polygon: DrawnPolygon
    session_areas: int = Field(ge=1)

    @model_validator(mode="after")
    def _territories_apart(self) -> Self:
        """No two boxes overlap, so a point belongs to one territory and one CRS rule."""
        boxes = self.territories
        for index, first in enumerate(boxes):
            for second in boxes[index + 1 :]:
                a, b = first.bbox, second.bbox
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    raise ValueError(f"territories {first.id} and {second.id} overlap")
        return self
