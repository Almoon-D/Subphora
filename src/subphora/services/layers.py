# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The official layers: tiles through the proxy, and what lies under a tapped point.

- A layer whose service has CORS and EPSG:3857 is drawn by the browser from the service;
  the proxy draws only the others: a service without CORS through its own GetMap, one
  without EPSG:3857 through the ArcGIS export the catalogue names for it. Always within the
  catalogue's limits (the client's per-host politeness, the cache lifetime, the layer's
  zoom range), and only PNG images.
- A tap is answered by the API for every theme, whatever its CORS: the API asks the
  service in a CRS it offers, parses the answer and keeps only the fields the catalogue
  allows, so no other field (protected data included) ever reaches the browser.
- A theme with regional layers (decision 0023) asks first the regional layer whose area
  holds the point; when it has nothing there, fails or times out, or its area's boundary
  cannot be read, the national layer answers, and the answer says so.
"""

from dataclasses import dataclass

from subphora.config import MapSettings, Settings
from subphora.config.map import ArcgisExport, FeatureInfo, Overlay
from subphora.config.regional import RegionalLayer, RegionalSettings
from subphora.config.sources import Service, SourcesSettings
from subphora.domain.layers import (
    Answer,
    Fallback,
    FallbackReason,
    InfoFeature,
    InfoField,
    LayerError,
    LayerFailure,
    LayerFeatureInfo,
    LayerLevel,
)
from subphora.domain.provenance import Provenance
from subphora.geo import (
    MAX_TILE_ZOOM,
    box_around,
    metres_per_pixel,
    reproject_box,
    tile_bounds,
    tile_exists,
)
from subphora.services.areas import AreaService
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure
from subphora.sources import CatalogueClient
from subphora.sources.wms import (
    WEB_MERCATOR,
    FeatureInfoError,
    allowed_fields,
    export_params,
    feature_info_params,
    getmap_params,
    is_png,
    parse_feature_info,
)
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now

_FALLBACK_REASONS = {
    LayerFailure.UPSTREAM_ERROR: FallbackReason.UPSTREAM_ERROR,
    LayerFailure.UPSTREAM_TIMEOUT: FallbackReason.UPSTREAM_TIMEOUT,
}


@dataclass(frozen=True, slots=True)
class Tile:
    """A PNG tile, and how long the browser may keep it (the catalogue's cache lifetime)."""

    content: bytes
    max_age_s: int


@dataclass(frozen=True, slots=True)
class _Drawn:
    """What the proxy and a tap need of a national or regional layer."""

    id: str
    service: Service
    layer: str
    style: str
    min_zoom: int
    # The deepest zoom the proxy draws it at; None: the overlays' max_zoom.
    max_zoom: int | None
    info: FeatureInfo | None
    export: ArcgisExport | None


@dataclass(frozen=True, slots=True)
class _Features:
    features: tuple[InfoFeature, ...]
    source: Provenance


def is_proxied(service: Service) -> bool:
    """Whether the browser needs the API to draw this service's layers."""
    return not (service.cors and service.web_mercator)


class LayerService:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        areas: AreaService,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._map: MapSettings = settings.map
        self._regional: RegionalSettings = settings.regional
        self._sources: SourcesSettings = settings.sources
        self._areas = areas

    def _theme(self, layer_id: str) -> Overlay:
        try:
            return self._map.overlays.layer(layer_id)
        except KeyError:
            raise LayerError(LayerFailure.UNKNOWN_LAYER, f"no layer {layer_id!r}") from None

    def _national(self, overlay: Overlay) -> _Drawn:
        return _Drawn(
            id=overlay.id,
            service=self._sources.service(overlay.service),
            layer=overlay.layer,
            style=overlay.style,
            min_zoom=overlay.min_zoom,
            max_zoom=None,
            info=overlay.info,
            export=overlay.export,
        )

    def _regional_drawn(self, layer: RegionalLayer) -> _Drawn:
        return _Drawn(
            id=layer.id,
            service=self._sources.service(layer.service),
            layer=layer.layer,
            style=layer.style,
            min_zoom=layer.min_zoom,
            max_zoom=layer.max_zoom,
            info=layer.info,
            export=None,
        )

    def _drawn(self, layer_id: str) -> _Drawn:
        """A national theme or a regional layer, by id."""
        try:
            return self._regional_drawn(self._regional.layer(layer_id))
        except KeyError:
            return self._national(self._theme(layer_id))

    def _check_zoom(self, drawn: _Drawn, zoom: float, *, tile: bool) -> None:
        # Beyond max_zoom the browser enlarges the last tiles: a tap there is still answered.
        if tile:
            top = self._map.overlays.max_zoom if drawn.max_zoom is None else drawn.max_zoom
        else:
            top = MAX_TILE_ZOOM
        if not drawn.min_zoom <= zoom <= top:
            raise LayerError(
                LayerFailure.OUTSIDE_ZOOM_RANGE,
                f"{drawn.id} is drawn from zoom {drawn.min_zoom} to {top}, not {zoom}",
            )

    async def tile(self, layer_id: str, z: int, x: int, y: int) -> Tile:
        """The PNG tile (z, x, y) of a proxied layer; raises LayerError."""
        drawn = self._drawn(layer_id)
        service = drawn.service
        if not is_proxied(service):
            raise LayerError(LayerFailure.NOT_PROXIED, f"{layer_id} is drawn from {service.id}")
        if not tile_exists(z, x, y):
            raise LayerError(LayerFailure.INVALID_TILE, f"no tile {z}/{x}/{y}")
        self._check_zoom(drawn, z, tile=True)
        size = self._map.overlays.tile_size
        box = tile_bounds(z, x, y)
        # Settings guarantee: a layer without EPSG:3857 names an export, and only it.
        if drawn.export is None:
            source, url = service, service.base_url
            params = getmap_params(drawn.layer, drawn.style, size, box)
        else:
            source = self._sources.service(drawn.export.service)
            url = source.base_url + drawn.export.path
            params = export_params(drawn.export.layers, size, box)
        fetched = await self._fetch(source, url, params)
        if not is_png(fetched.content):
            raise LayerError(
                LayerFailure.UPSTREAM_ERROR, f"{source.publisher}: the answer is not a PNG"
            )
        await self._fetcher.store(source, fetched)
        return Tile(fetched.content, source.politeness.cache_lifetime_s)

    async def info(self, layer_id: str, lon: float, lat: float, zoom: float) -> LayerFeatureInfo:
        """The allowed fields of the theme's features at (lon, lat), from the regional layer
        whose area holds the point when it answers, else the national one; raises
        LayerError when neither can answer."""
        overlay = self._theme(layer_id)
        fallbacks: list[Fallback] = []
        empty: LayerFeatureInfo | None = None
        failed: LayerError | None = None
        for layer in self._regional.of_theme(overlay.id):
            if layer.info is None or not layer.min_zoom <= zoom <= MAX_TILE_ZOOM:
                continue
            try:
                area_id = await self._holding_area(layer, lon, lat)
            except LayerError as exc:
                fallbacks.append(
                    Fallback(layer_id=layer.id, reason=FallbackReason.BOUNDARY_UNAVAILABLE)
                )
                failed = failed or exc
                continue
            if area_id is None:
                continue
            drawn = self._regional_drawn(layer)
            try:
                found = await self._features(drawn, lon, lat, zoom)
            except LayerError as exc:
                fallbacks.append(Fallback(layer_id=layer.id, reason=_FALLBACK_REASONS[exc.failure]))
                failed = failed or exc
                continue
            answer = Answer(
                level=LayerLevel.REGIONAL,
                layer_id=layer.id,
                publisher=drawn.service.publisher,
                detail=layer.evidence.detail,
                area_id=area_id,
            )
            result = self._result(overlay.id, found, answer, fallbacks)
            if found.features:
                return result
            fallbacks.append(Fallback(layer_id=layer.id, reason=FallbackReason.NO_FEATURE))
            empty = empty or result
        return await self._national_info(overlay, lon, lat, zoom, fallbacks, empty, failed)

    async def _national_info(
        self,
        overlay: Overlay,
        lon: float,
        lat: float,
        zoom: float,
        fallbacks: list[Fallback],
        empty: LayerFeatureInfo | None,
        failed: LayerError | None,
    ) -> LayerFeatureInfo:
        national = self._national(overlay)
        if national.info is None or not national.min_zoom <= zoom <= MAX_TILE_ZOOM:
            # The national layer cannot answer here: a regional "nothing" is the answer.
            if empty is not None:
                return empty
            if failed is not None:
                raise failed
            if national.info is None:
                raise LayerError(LayerFailure.NO_FEATURE_INFO, f"{overlay.id} has no feature info")
            self._check_zoom(national, zoom, tile=False)
        found = await self._features(national, lon, lat, zoom)
        answer = Answer(
            level=LayerLevel.NATIONAL,
            layer_id=overlay.id,
            publisher=national.service.publisher,
            detail=overlay.detail,
        )
        return self._result(overlay.id, found, answer, fallbacks)

    @staticmethod
    def _result(
        theme: str, found: _Features, answer: Answer, fallbacks: list[Fallback]
    ) -> LayerFeatureInfo:
        return LayerFeatureInfo(
            layer_id=theme,
            features=found.features,
            source=found.source,
            answered_by=answer,
            fallbacks=tuple(fallbacks),
        )

    async def _holding_area(self, layer: RegionalLayer, lon: float, lat: float) -> str | None:
        """The first of the layer's areas that holds the point, or None."""
        for area_id in layer.areas:
            if await self._areas.holds(area_id, lon, lat):
                return area_id
        return None

    async def _features(self, drawn: _Drawn, lon: float, lat: float, zoom: float) -> _Features:
        info = drawn.info
        if info is None:  # pragma: no cover - callers check first
            raise LayerError(LayerFailure.NO_FEATURE_INFO, f"{drawn.id} has no feature info")
        service = drawn.service
        settings = self._map.overlays
        size = settings.info_image_px
        half = metres_per_pixel(zoom, settings.tile_size) * size / 2
        box = box_around((lon, lat), half)
        crs = WEB_MERCATOR if service.web_mercator else service.crs[0]
        if crs != WEB_MERCATOR:
            box = reproject_box(box, crs)
        params = feature_info_params(
            drawn.layer,
            drawn.style,
            crs,
            box,
            size,
            info.info_format,
            settings.info_feature_count,
        )
        fetched = await self._fetch(service, service.base_url, params)
        try:
            features = parse_feature_info(fetched.content, info.parser)
        except FeatureInfoError as exc:
            raise LayerError(LayerFailure.UPSTREAM_ERROR, f"{service.publisher}: {exc}") from exc
        await self._fetcher.store(service, fetched)
        kept = allowed_fields(features, info.fields)
        return _Features(
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
