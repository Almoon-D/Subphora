# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``GET /api/map``: the view and every layer the front end draws, from the map config and
the source catalogue, so that no host, layer name or attribution is written in the front end.

The base maps, the cadastre and the overlays whose services have CORS and EPSG:3857 are
drawn by the browser from the service; the other overlays come from the API's tile proxy.
"""

from urllib.parse import urlencode

from subphora.config import Settings
from subphora.config.map import BaseMap as BaseMapSettings
from subphora.config.map import Overlay as OverlaySettings
from subphora.domain import DomainModel
from subphora.services.layers import is_proxied
from subphora.sources.wms import WEB_MERCATOR, legend_params

# MapLibre replaces these in a tile URL.
_TILE_PLACEHOLDERS = {"tilematrix": "{z}", "tilerow": "{y}", "tilecol": "{x}"}
_BBOX_PLACEHOLDER = "{bbox-epsg-3857}"
# The proxy's route (api/app.py), with MapLibre's placeholders.
PROXY_TILES = "/api/layers/{layer_id}/tiles/{{z}}/{{x}}/{{y}}"


class View(DomainModel):
    longitude: float
    latitude: float
    zoom: float


class BaseMap(DomainModel):
    id: str
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
    visible: bool
    opacity: float


class Overlay(DomainModel):
    id: str
    group: str
    service_id: str
    # Absolute URLs to the service, or the API's relative proxy route.
    tiles: tuple[str, ...]
    proxied: bool
    tile_size: int
    min_zoom: int
    max_zoom: int
    opacity: float
    visible: bool
    # None: the service has no legend a person can read.
    legend_url: str | None
    # Whether a tap asks the API what lies under it.
    feature_info: bool
    attribution: str
    # ISO 3166 codes of the areas the service covers (ES, ES-AN…).
    coverage: tuple[str, ...]


class MapConfig(DomainModel):
    initial_view: View
    parcel_padding_px: int
    base_maps: tuple[BaseMap, ...]
    cadastre: CadastreOverlay
    overlay_groups: tuple[str, ...]
    overlays: tuple[Overlay, ...]


def _with_query(base_url: str, query: str) -> str:
    # Some base URLs carry a query of their own (?map=…).
    return f"{base_url}{'&' if '?' in base_url else '?'}{query}"


def _base_map(settings: Settings, base: BaseMapSettings) -> BaseMap:
    service = settings.sources.service(base.service)
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
    return BaseMap(
        id=base.id,
        service_id=service.id,
        tiles=(_with_query(service.base_url, template),),
        tile_size=base.tile_size,
        max_zoom=base.max_zoom,
        attribution=service.attribution,
    )


def _overlay(settings: Settings, overlay: OverlaySettings) -> Overlay:
    service = settings.sources.service(overlay.service)
    overlays = settings.map.overlays
    proxied = is_proxied(service)
    if proxied:
        tiles = PROXY_TILES.format(layer_id=overlay.id)
    else:
        size = str(overlays.tile_size)
        query = urlencode(
            {
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetMap",
                "LAYERS": overlay.layer,
                "STYLES": overlay.style,
                "CRS": WEB_MERCATOR,
                "WIDTH": size,
                "HEIGHT": size,
                "FORMAT": "image/png",
                "TRANSPARENT": "true",
            }
        )
        tiles = _with_query(service.base_url, f"{query}&BBOX={_BBOX_PLACEHOLDER}")
    match overlay.legend.kind:
        case "wms":
            legend: str | None = _with_query(
                service.base_url, urlencode(legend_params(overlay.layer, overlay.style))
            )
        case "url":
            legend = overlay.legend.url
        case "none":
            legend = None
    return Overlay(
        id=overlay.id,
        group=overlay.group,
        service_id=service.id,
        tiles=(tiles,),
        proxied=proxied,
        tile_size=overlays.tile_size,
        min_zoom=overlay.min_zoom,
        max_zoom=overlays.max_zoom,
        opacity=overlay.opacity,
        visible=overlay.id in overlays.visible_at_start,
        legend_url=legend,
        feature_info=overlay.info is not None,
        attribution=service.attribution,
        coverage=tuple(service.coverage),
    )


def map_config(settings: Settings) -> MapConfig:
    cadastre = settings.map.cadastre
    cadastre_service = settings.sources.service(cadastre.service)
    view = settings.map.initial_view
    return MapConfig(
        initial_view=View(longitude=view.longitude, latitude=view.latitude, zoom=view.zoom),
        parcel_padding_px=settings.map.parcel_padding_px,
        base_maps=tuple(_base_map(settings, base) for base in settings.map.base_maps),
        cadastre=CadastreOverlay(
            service_id=cadastre_service.id,
            url=cadastre_service.base_url,
            params={
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetMap",
                "LAYERS": cadastre.layer,
                "STYLES": cadastre.style,
                "CRS": WEB_MERCATOR,
                "FORMAT": cadastre.format,
                "TRANSPARENT": "true",
            },
            min_zoom=cadastre.min_zoom,
            refresh_delay_ms=cadastre.refresh_delay_ms,
            max_image_px=cadastre.max_image_px,
            attribution=cadastre_service.attribution,
            visible=cadastre.visible,
            opacity=cadastre.opacity,
        ),
        overlay_groups=tuple(settings.map.overlays.groups),
        overlays=tuple(_overlay(settings, overlay) for overlay in settings.map.overlays.layers),
    )
