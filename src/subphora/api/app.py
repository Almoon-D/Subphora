# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The HTTP API: ``create_app(settings)``, served by ``subphora serve``.

- ``GET /api/parcels/{reference}``: a cadastral parcel (outline in EPSG:4326, area,
  municipality, province), or an error whose ``code`` says why there is none.
- ``GET /api/map``: the base maps, the cadastral overlay and the official layers the front
  end draws, built from the catalogues so that no host or attribution is written in it.
- ``GET /api/layers/{id}/tiles/{z}/{x}/{y}``: a PNG tile of an official layer the browser
  cannot draw from its service (no CORS or no EPSG:3857).
- ``GET /api/layers/{id}/info?lon=&lat=&zoom=``: the allowed fields of the layer's
  features under a tapped point.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import fastapi
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from subphora import __version__
from subphora.api.map import MapConfig, map_config
from subphora.config import REPO_ROOT, Settings
from subphora.domain.layers import LayerError, LayerFailure, LayerFeatureInfo
from subphora.domain.parcels import CadastralParcel, LookupFailure, ParcelLookupError
from subphora.geo import MAX_TILE_ZOOM
from subphora.services.layers import LayerService
from subphora.services.parcels import ParcelService
from subphora.sources import CatalogueClient
from subphora.sources.client import Transport
from subphora.store import FileCache

_log = logging.getLogger(__name__)

# Each failure has its own status, so the front end and logs tell them apart.
_STATUS = {
    LookupFailure.MALFORMED: 400,
    LookupFailure.NOT_FOUND: 404,
    LookupFailure.NOT_SUPPORTED: 422,
    LookupFailure.UPSTREAM_ERROR: 502,
    LookupFailure.UPSTREAM_TIMEOUT: 504,
}
_LAYER_STATUS = {
    LayerFailure.UNKNOWN_LAYER: 404,
    LayerFailure.NOT_PROXIED: 404,
    LayerFailure.NO_FEATURE_INFO: 404,
    LayerFailure.INVALID_TILE: 400,
    LayerFailure.OUTSIDE_ZOOM_RANGE: 422,
    LayerFailure.UPSTREAM_ERROR: 502,
    LayerFailure.UPSTREAM_TIMEOUT: 504,
}
_UPSTREAM_LAYER_FAILURES = (LayerFailure.UPSTREAM_ERROR, LayerFailure.UPSTREAM_TIMEOUT)
_PNG = "image/png"
_ZOOM = Query(ge=0, le=MAX_TILE_ZOOM)
_TILE_INDEX = fastapi.Path(ge=0)


def create_app(
    settings: Settings,
    root: Path = REPO_ROOT,
    transport: Transport | None = None,
) -> FastAPI:
    """The application; ``transport`` replaces the network in tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One client for the life of the server: its per-host limits hold across requests.
        async with CatalogueClient(settings.sources, __version__, transport) as client:
            cache = FileCache(settings.store.cache_path(root))
            app.state.parcels = ParcelService(client, settings.sources, cache)
            app.state.layers = LayerService(client, settings, cache)
            yield

    app = FastAPI(title="Subphora", version=__version__, lifespan=lifespan)
    map_body = map_config(settings)

    @app.exception_handler(ParcelLookupError)
    async def lookup_failed(_request: Request, exc: ParcelLookupError) -> JSONResponse:
        if exc.failure in (LookupFailure.UPSTREAM_ERROR, LookupFailure.UPSTREAM_TIMEOUT):
            _log.warning("parcel lookup failed upstream: %s", exc.detail)
        # `code` is for the front end, which shows its own message; `detail` is for logs.
        return JSONResponse(
            status_code=_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    @app.exception_handler(LayerError)
    async def layer_failed(_request: Request, exc: LayerError) -> JSONResponse:
        if exc.failure in _UPSTREAM_LAYER_FAILURES:
            _log.warning("layer request failed upstream: %s", exc.detail)
        return JSONResponse(
            status_code=_LAYER_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    @app.get("/api/parcels/{reference}")
    async def parcel(reference: str, request: Request) -> CadastralParcel:
        service: ParcelService = request.app.state.parcels
        return await service.lookup(reference)

    @app.get("/api/map")
    async def map_layers() -> MapConfig:
        return map_body

    @app.get("/api/layers/{layer_id}/tiles/{z}/{x}/{y}", response_class=Response)
    async def layer_tile(
        layer_id: str,
        z: Annotated[int, _TILE_INDEX],
        x: Annotated[int, _TILE_INDEX],
        y: Annotated[int, _TILE_INDEX],
        request: Request,
    ) -> Response:
        layers: LayerService = request.app.state.layers
        tile = await layers.tile(layer_id, z, x, y)
        return Response(
            content=tile.content,
            media_type=_PNG,
            headers={"Cache-Control": f"public, max-age={tile.max_age_s}"},
        )

    @app.get("/api/layers/{layer_id}/info")
    async def layer_info(
        layer_id: str,
        lon: Annotated[float, Query(ge=-180, le=180)],
        lat: Annotated[float, Query(ge=-85, le=85)],
        zoom: Annotated[float, _ZOOM],
        request: Request,
    ) -> LayerFeatureInfo:
        layers: LayerService = request.app.state.layers
        return await layers.info(layer_id, lon, lat, zoom)

    return app
