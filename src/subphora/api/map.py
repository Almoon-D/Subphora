# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``GET /api/map``: the view and every layer the front end draws, from the map config and
the source catalogue, so that no host, layer name or attribution is written in the front end.

The base maps, the cadastre and the overlays whose services have CORS and EPSG:3857 are
drawn by the browser from the service; the other overlays come from the API's tile proxy.
Each overlay is one map theme: its national layer, and the regional layers that detail it
inside their areas (decision 0023), which the browser clips to the boundaries it reads
from ``GET /api/areas/{id}``.
"""

from urllib.parse import urlencode

from subphora.config import Settings
from subphora.config.map import BaseMap as BaseMapSettings
from subphora.config.map import Legend
from subphora.config.map import Overlay as OverlaySettings
from subphora.config.regional import RegionalLayer as RegionalSettings
from subphora.config.sources import Service
from subphora.domain import DomainModel
from subphora.domain.layers import LayerDetail
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


class RegionalOverlay(DomainModel):
    """A regional layer, drawn inside its areas over its theme's national layer."""

    id: str
    service_id: str
    publisher: str
    tiles: tuple[str, ...]
    proxied: bool
    min_zoom: int
    # The deepest zoom its service draws; the browser enlarges that level beyond it.
    max_zoom: int
    # The areas it is drawn and asked inside, and the box enclosing them all.
    area_ids: tuple[str, ...]
    bounds: tuple[float, float, float, float]
    legend_url: str | None
    feature_info: bool
    attribution: str
    detail: LayerDetail


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
    # Whether a tap asks the API what the national layer holds (each regional layer says
    # the same of itself, inside its bounds).
    feature_info: bool
    attribution: str
    publisher: str
    detail: LayerDetail
    regional: tuple[RegionalOverlay, ...]


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


def _tiles(settings: Settings, service: Service, layer_id: str, layer: str, style: str) -> str:
    if is_proxied(service):
        return PROXY_TILES.format(layer_id=layer_id)
    size = str(settings.map.overlays.tile_size)
    query = urlencode(
        {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": layer,
            "STYLES": style,
            "CRS": WEB_MERCATOR,
            "WIDTH": size,
            "HEIGHT": size,
            "FORMAT": "image/png",
            "TRANSPARENT": "true",
        }
    )
    return _with_query(service.base_url, f"{query}&BBOX={_BBOX_PLACEHOLDER}")


def _legend(service: Service, legend: Legend, layer: str, style: str) -> str | None:
    match legend.kind:
        case "wms":
            return _with_query(service.base_url, urlencode(legend_params(layer, style)))
        case "url":
            return legend.url
        case "none":
            return None


def _regional(settings: Settings, layer: RegionalSettings) -> RegionalOverlay:
    service = settings.sources.service(layer.service)
    boxes = [settings.regional.area(area_id).bbox for area_id in layer.areas]
    return RegionalOverlay(
        id=layer.id,
        service_id=service.id,
        publisher=service.publisher,
        tiles=(_tiles(settings, service, layer.id, layer.layer, layer.style),),
        proxied=is_proxied(service),
        min_zoom=layer.min_zoom,
        max_zoom=settings.map.overlays.max_zoom if layer.max_zoom is None else layer.max_zoom,
        area_ids=tuple(layer.areas),
        bounds=(
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ),
        legend_url=_legend(service, layer.legend, layer.layer, layer.style),
        feature_info=layer.info is not None,
        attribution=service.attribution,
        detail=layer.evidence.detail,
    )


def _overlay(settings: Settings, overlay: OverlaySettings) -> Overlay:
    service = settings.sources.service(overlay.service)
    overlays = settings.map.overlays
    regional = tuple(_regional(settings, layer) for layer in settings.regional.of_theme(overlay.id))
    return Overlay(
        id=overlay.id,
        group=overlay.group,
        service_id=service.id,
        tiles=(_tiles(settings, service, overlay.id, overlay.layer, overlay.style),),
        proxied=is_proxied(service),
        tile_size=overlays.tile_size,
        min_zoom=overlay.min_zoom,
        max_zoom=overlays.max_zoom,
        opacity=overlay.opacity,
        visible=overlay.id in overlays.visible_at_start,
        legend_url=_legend(service, overlay.legend, overlay.layer, overlay.style),
        feature_info=overlay.info is not None,
        attribution=service.attribution,
        publisher=service.publisher,
        detail=overlay.detail,
        regional=regional,
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
