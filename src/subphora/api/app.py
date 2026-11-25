# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The HTTP API: ``create_app(settings)``, served by ``subphora serve``.

- ``GET /api/search?q=``: every reading of what was typed (a cadastral or SIGPAC
  reference, coordinates, CartoCiudad's places for a name), each with the path that
  resolves it, or an error whose ``code`` says why there is none.
- ``GET /api/aoi/cadastral/{reference}``, ``/api/aoi/sigpac/{code}``,
  ``/api/aoi/place?type=&id=``, ``/api/aoi/point?crs=&x=&y=&origin=`` and
  ``POST /api/aoi/polygon`` (a GeoJSON Polygon drawn on the map): the area of interest.
- ``GET /api/map``: the base maps, the cadastral overlay and the official layers the front
  end draws, built from the catalogues so that no host or attribution is written in it.
- ``GET /api/layers/{id}/tiles/{z}/{x}/{y}``: a PNG tile of an official layer, national or
  regional, the browser cannot draw from its service (no CORS or no EPSG:3857).
- ``GET /api/layers/{id}/info?lon=&lat=&zoom=``: the allowed fields of a map theme's
  features under a tapped point, from the regional layer whose area holds it or the
  national one, saying which answered.
- ``GET /api/areas/{id}``: the official boundary a regional layer is drawn inside.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import fastapi
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from subphora import __version__
from subphora.api.map import MapConfig, map_config
from subphora.config import REPO_ROOT, Settings
from subphora.domain import DomainModel
from subphora.domain.aoi import AoiOrigin, AreaOfInterest, SearchAnswer, SearchError, SearchFailure
from subphora.domain.areas import AreaBoundary
from subphora.domain.layers import LayerError, LayerFailure, LayerFeatureInfo
from subphora.domain.parcels import Position
from subphora.geo import MAX_TILE_ZOOM
from subphora.services.aoi import AoiService
from subphora.services.areas import AreaService
from subphora.services.layers import LayerService
from subphora.services.parcels import ParcelService
from subphora.sources import CatalogueClient
from subphora.sources.client import Transport
from subphora.store import FileCache

_log = logging.getLogger(__name__)

# Each failure has its own status, so the front end and logs tell them apart.
_STATUS = {
    SearchFailure.EMPTY: 400,
    SearchFailure.MALFORMED_REFERENCE: 400,
    SearchFailure.MALFORMED_SIGPAC: 400,
    SearchFailure.MALFORMED_COORDINATES: 400,
    SearchFailure.INVALID_POLYGON: 400,
    SearchFailure.NOT_FOUND: 404,
    SearchFailure.NO_MATCH: 404,
    SearchFailure.WRONG_UTM_ZONE: 422,
    SearchFailure.OUTSIDE_COUNTRY: 422,
    SearchFailure.TERRITORY_NOT_SUPPORTED: 422,
    SearchFailure.UPSTREAM_ERROR: 502,
    SearchFailure.UPSTREAM_TIMEOUT: 504,
}
_UPSTREAM_FAILURES = (SearchFailure.UPSTREAM_ERROR, SearchFailure.UPSTREAM_TIMEOUT)
_LAYER_STATUS = {
    LayerFailure.UNKNOWN_LAYER: 404,
    LayerFailure.UNKNOWN_AREA: 404,
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


class DrawnPolygon(DomainModel):
    """The body of ``POST /api/aoi/polygon``: a GeoJSON Polygon of one ring, no holes."""

    type: Literal["Polygon"]
    coordinates: tuple[tuple[Position, ...]] = Field(min_length=1, max_length=1)


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
            parcels = ParcelService(client, settings.sources, cache)
            app.state.aoi = AoiService(client, settings, cache, parcels)
            app.state.areas = AreaService(client, settings, cache)
            app.state.layers = LayerService(client, settings, cache, app.state.areas)
            yield

    app = FastAPI(title="Subphora", version=__version__, lifespan=lifespan)
    map_body = map_config(settings)

    @app.exception_handler(SearchError)
    async def search_failed(_request: Request, exc: SearchError) -> JSONResponse:
        if exc.failure in _UPSTREAM_FAILURES:
            # The detail names the service and the failure, never the query.
            _log.warning("search failed upstream: %s", exc.detail)
        # `code` and `source` are for the front end, which shows its own message; `detail`
        # is for people reading the answer.
        return JSONResponse(
            status_code=_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail, "source": exc.source},
        )

    @app.exception_handler(LayerError)
    async def layer_failed(_request: Request, exc: LayerError) -> JSONResponse:
        if exc.failure in _UPSTREAM_LAYER_FAILURES:
            _log.warning("layer request failed upstream: %s", exc.detail)
        return JSONResponse(
            status_code=_LAYER_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    def aoi(request: Request) -> AoiService:
        service: AoiService = request.app.state.aoi
        return service

    @app.get("/api/search")
    async def search(q: str, request: Request) -> SearchAnswer:
        return await aoi(request).search(q)

    @app.get("/api/aoi/cadastral/{reference}")
    async def cadastral(reference: str, request: Request) -> AreaOfInterest:
        return await aoi(request).cadastral(reference)

    @app.get("/api/aoi/sigpac/{code}")
    async def sigpac(code: str, request: Request) -> AreaOfInterest:
        return await aoi(request).sigpac(code)

    @app.get("/api/aoi/place")
    async def place(
        place_type: Annotated[str, Query(alias="type", min_length=1)],
        place_id: Annotated[str, Query(alias="id", min_length=1)],
        request: Request,
    ) -> AreaOfInterest:
        return await aoi(request).place(place_type, place_id)

    @app.get("/api/aoi/point")
    async def point(
        crs: str, x: float, y: float, origin: AoiOrigin, request: Request
    ) -> AreaOfInterest:
        return await aoi(request).point(crs, x, y, origin)

    @app.post("/api/aoi/polygon")
    async def polygon(request: Request) -> AreaOfInterest:
        try:
            drawn = DrawnPolygon.model_validate_json(await request.body())
        except ValidationError as exc:
            raise SearchError(
                SearchFailure.INVALID_POLYGON, "the body is not a GeoJSON Polygon of one ring"
            ) from exc
        return await aoi(request).polygon(drawn.coordinates[0])

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

    @app.get("/api/areas/{area_id}")
    async def area(area_id: str, request: Request, response: Response) -> AreaBoundary:
        areas: AreaService = request.app.state.areas
        boundary = await areas.boundary(area_id)
        # The browser may keep it as long as the server's cache does.
        lifetime = settings.sources.service(boundary.source.service_id).politeness
        response.headers["Cache-Control"] = f"public, max-age={lifetime.cache_lifetime_s}"
        return boundary

    return app
