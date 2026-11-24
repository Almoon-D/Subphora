# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The official layers: tiles through the proxy, and what lies under a tapped point.

- A layer whose service has CORS and EPSG:3857 is drawn by the browser from the service;
  the proxy draws only the others, from the ArcGIS export the catalogue names for them,
  within the catalogue's limits (the client's per-host politeness, the cache lifetime, the
  layer's zoom range), and only PNG images.
- A tap is answered by the API for every layer, whatever its CORS: the API asks the
  service in a CRS it offers, parses the answer and keeps only the fields the map
  catalogue allows, so no other field (protected data included) ever reaches the browser.
"""

from dataclasses import dataclass

from subphora.config import MapSettings, Settings
from subphora.config.map import Overlay
from subphora.config.sources import Service, SourcesSettings
from subphora.domain.layers import (
    InfoFeature,
    InfoField,
    LayerError,
    LayerFailure,
    LayerFeatureInfo,
)
from subphora.geo import (
    MAX_TILE_ZOOM,
    box_around,
    metres_per_pixel,
    reproject_box,
    tile_bounds,
    tile_exists,
)
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure
from subphora.sources import CatalogueClient
from subphora.sources.wms import (
    WEB_MERCATOR,
    FeatureInfoError,
    allowed_fields,
    export_params,
    feature_info_params,
    is_png,
    parse_feature_info,
)
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now


@dataclass(frozen=True, slots=True)
class Tile:
    """A PNG tile, and how long the browser may keep it (the catalogue's cache lifetime)."""

    content: bytes
    max_age_s: int


def is_proxied(service: Service) -> bool:
    """Whether the browser needs the API to draw this service's layers."""
    return not (service.cors and service.web_mercator)


class LayerService:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._map: MapSettings = settings.map
        self._sources: SourcesSettings = settings.sources

    def _overlay(self, layer_id: str) -> tuple[Overlay, Service]:
        try:
            overlay = self._map.overlays.layer(layer_id)
        except KeyError:
            raise LayerError(LayerFailure.UNKNOWN_LAYER, f"no layer {layer_id!r}") from None
        return overlay, self._sources.service(overlay.service)

    def _check_zoom(self, overlay: Overlay, zoom: float, *, tile: bool) -> None:
        # Beyond max_zoom the browser enlarges the last tiles: a tap there is still answered.
        top = self._map.overlays.max_zoom if tile else MAX_TILE_ZOOM
        if not overlay.min_zoom <= zoom <= top:
            raise LayerError(
                LayerFailure.OUTSIDE_ZOOM_RANGE,
                f"{overlay.id} is drawn from zoom {overlay.min_zoom} to {top}, not {zoom}",
            )

    async def tile(self, layer_id: str, z: int, x: int, y: int) -> Tile:
        """The PNG tile (z, x, y) of a proxied layer; raises LayerError."""
        overlay, service = self._overlay(layer_id)
        # Settings guarantee: a layer the browser cannot draw names an export, and only it.
        export = overlay.export
        if export is None:
            raise LayerError(LayerFailure.NOT_PROXIED, f"{layer_id} is drawn from {service.id}")
        if not tile_exists(z, x, y):
            raise LayerError(LayerFailure.INVALID_TILE, f"no tile {z}/{x}/{y}")
        self._check_zoom(overlay, z, tile=True)
        size = self._map.overlays.tile_size
        source = self._sources.service(export.service)
        url = source.base_url + export.path
        params = export_params(export.layers, size, tile_bounds(z, x, y))
        fetched = await self._fetch(source, url, params)
        if not is_png(fetched.content):
            raise LayerError(
                LayerFailure.UPSTREAM_ERROR, f"{source.publisher}: the answer is not a PNG"
            )
        await self._fetcher.store(source, fetched)
        return Tile(fetched.content, source.politeness.cache_lifetime_s)

    async def info(self, layer_id: str, lon: float, lat: float, zoom: float) -> LayerFeatureInfo:
        """The allowed fields of the layer's features at (lon, lat); raises LayerError."""
        overlay, service = self._overlay(layer_id)
        if overlay.info is None:
            raise LayerError(LayerFailure.NO_FEATURE_INFO, f"{layer_id} has no feature info")
        self._check_zoom(overlay, zoom, tile=False)
        settings = self._map.overlays
        size = settings.info_image_px
        half = metres_per_pixel(zoom, settings.tile_size) * size / 2
        box = box_around((lon, lat), half)
        crs = WEB_MERCATOR if service.web_mercator else service.crs[0]
        if crs != WEB_MERCATOR:
            box = reproject_box(box, crs)
        params = feature_info_params(
            overlay.layer,
            overlay.style,
            crs,
            box,
            size,
            overlay.info.info_format,
            settings.info_feature_count,
        )
        fetched = await self._fetch(service, service.base_url, params)
        try:
            features = parse_feature_info(fetched.content, overlay.info.parser)
        except FeatureInfoError as exc:
            raise LayerError(LayerFailure.UPSTREAM_ERROR, f"{service.publisher}: {exc}") from exc
        await self._fetcher.store(service, fetched)
        kept = allowed_fields(features, overlay.info.fields)
        return LayerFeatureInfo(
            layer_id=overlay.id,
            features=tuple(
                InfoFeature(fields=tuple(InfoField(name=n, value=v) for n, v in feature))
                for feature in kept
            ),
            source=fetched.provenance,
        )

    async def _fetch(self, service: Service, url: str, params: dict[str, str]) -> Fetched:
        try:
            return await self._fetcher.fetch(service, url, params)
        except UpstreamFailure as exc:
            failure = LayerFailure.UPSTREAM_TIMEOUT if exc.timeout else LayerFailure.UPSTREAM_ERROR
            raise LayerError(failure, exc.detail) from exc
