# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/map.yaml``: the layers and view the front end draws."""

from pydantic import Field, PositiveInt

from subphora.config.base import Section


class InitialView(Section):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-85, le=85)
    zoom: float = Field(ge=0, le=22)


class BaseLayer(Section):
    """A WMTS tile layer in a Web Mercator tile matrix set."""

    service: str
    layer: str
    format: str
    tile_matrix_set: str
    tile_size: PositiveInt
    max_zoom: int = Field(ge=0, le=24)


class CadastreLayer(Section):
    """A WMS layer drawn as one untiled image per view."""

    service: str
    layer: str
    style: str
    format: str
    min_zoom: float = Field(ge=0, le=24)
    refresh_delay_ms: int = Field(ge=0)
    max_image_px: PositiveInt


class MapSettings(Section):
    initial_view: InitialView
    parcel_padding_px: int = Field(ge=0)
    base: BaseLayer
    cadastre: CadastreLayer
