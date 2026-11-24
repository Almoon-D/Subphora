# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``GET /api/map``: the layers the front end draws, from the map config and the catalogue.

The browser calls PNOA and Catastro directly (both send CORS and offer EPSG:3857), so the
API only tells it where and how: the URLs come from the source catalogue, never from the
front end's code.
"""

from urllib.parse import urlencode

from subphora.config import Settings
from subphora.domain import DomainModel

# MapLibre replaces these in a tile URL.
_TILE_PLACEHOLDERS = {"tilematrix": "{z}", "tilerow": "{y}", "tilecol": "{x}"}
# Web Mercator: MapLibre's own projection, the only one the browser draws.
_WEB_MERCATOR = "EPSG:3857"


class View(DomainModel):
    longitude: float
    latitude: float
    zoom: float


class BaseMap(DomainModel):
    service_id: str
    tiles: tuple[str, ...]
    tile_size: int
    max_zoom: int
    attribution: str


class CadastreOverlay(DomainModel):
    service_id: str
    # GetMap URL without the view: the front end adds BBOX, WIDTH and HEIGHT.
    url: str
    params: dict[str, str]
    min_zoom: float
    refresh_delay_ms: int
    max_image_px: int
    attribution: str


class MapConfig(DomainModel):
    initial_view: View
    parcel_padding_px: int
    base: BaseMap
    cadastre: CadastreOverlay


def map_config(settings: Settings) -> MapConfig:
    base = settings.map.base
    base_service = settings.sources.service(base.service)
    query = {
        "service": "WMTS",
        "request": "GetTile",
        "version": "1.0.0",
        "layer": base.layer,
        "style": "default",
        "format": base.format,
        "tilematrixset": base.tile_matrix_set,
    }
    # The placeholders must reach MapLibre unescaped.
    template = "&".join(
        [urlencode(query)] + [f"{key}={value}" for key, value in _TILE_PLACEHOLDERS.items()]
    )
    cadastre = settings.map.cadastre
    cadastre_service = settings.sources.service(cadastre.service)
    view = settings.map.initial_view
    return MapConfig(
        initial_view=View(longitude=view.longitude, latitude=view.latitude, zoom=view.zoom),
        parcel_padding_px=settings.map.parcel_padding_px,
        base=BaseMap(
            service_id=base_service.id,
            tiles=(f"{base_service.base_url}?{template}",),
            tile_size=base.tile_size,
            max_zoom=base.max_zoom,
            attribution=base_service.attribution,
        ),
        cadastre=CadastreOverlay(
            service_id=cadastre_service.id,
            url=cadastre_service.base_url,
            params={
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetMap",
                "LAYERS": cadastre.layer,
                "STYLES": cadastre.style,
                "CRS": _WEB_MERCATOR,
                "FORMAT": cadastre.format,
                "TRANSPARENT": "true",
            },
            min_zoom=cadastre.min_zoom,
            refresh_delay_ms=cadastre.refresh_delay_ms,
            max_image_px=cadastre.max_image_px,
            attribution=cadastre_service.attribution,
        ),
    )
