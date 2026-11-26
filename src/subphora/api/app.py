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
- ``GET /api/national``: the national water-potential map's layers, legends and regions.
- ``GET /api/national/tiles/{layer}/{z}/{x}/{y}``: a PNG tile of a national layer.
- ``GET /api/national/explain?lon=&lat=``: the index at a point with its confidence, the
  contribution and source of every input, and the inputs missing there.
- ``POST /api/parcel`` (an area of interest): the job of its detailed map, started unless
  it is running or done; ``GET /api/parcel/{id}``: the job, with the analysis (summary
  and ranked candidates) and its layers once done.
- ``GET /api/parcel/{id}/explain?lon=&lat=``: the detailed map's estimate at a point.
- ``GET /api/parcel/{id}/layers/{layer}``: a layer of the detailed map as one PNG.
- ``GET /api/legal?lon=&lat=&region=``: the legal status at a point of a region (ISO
  3166-2): its water authority, groundwater body and status, the rules that apply there
  with their sources and dates, the verdict and the disclaimer; an area's legal panel.
- ``POST /api/section`` (a line's two ends): the interpretive geological cross-section
  under it, with the confidence of every cell and "unknown" below the evidence.
- ``POST /api/field/observations`` (a batch of field records): each stored once, its
  outcome (created, duplicate or conflict) in the answer; a retried batch changes nothing.
- ``PUT /api/field/observations/{id}/media``: a photo's or voice memo's file, once its
  record is stored and only if it is the file the record declared.
"""

import logging
from collections.abc import AsyncIterator
from concurrent.futures import Executor, ProcessPoolExecutor
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import fastapi
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from subphora import __version__
from subphora.api.map import MapConfig, map_config
from subphora.api.national import NationalMap, national_map
from subphora.api.parcel import ParcelAnswer, parcel_answer
from subphora.config import REPO_ROOT, Settings
from subphora.domain import DomainModel
from subphora.domain.aoi import AoiOrigin, AreaOfInterest, SearchAnswer, SearchError, SearchFailure
from subphora.domain.areas import AreaBoundary
from subphora.domain.field import (
    FieldError,
    FieldFailure,
    MediaAnswer,
    Observation,
    Outcome,
    SyncAnswer,
)
from subphora.domain.layers import LayerError, LayerFailure, LayerFeatureInfo
from subphora.domain.legal import LegalStatus
from subphora.domain.parcel_map import JobState, ParcelError, ParcelExplanation, ParcelFailure
from subphora.domain.parcels import Position
from subphora.domain.potential import CellExplanation, NationalError, NationalFailure
from subphora.domain.section import CrossSection, SectionError, SectionFailure
from subphora.geo import MAX_TILE_ZOOM
from subphora.services.aoi import AoiService
from subphora.services.areas import AreaService
from subphora.services.field import FieldService
from subphora.services.layers import LayerService
from subphora.services.legal import LegalService
from subphora.services.national_map import NationalMapService
from subphora.services.parcel import ParcelMapService
from subphora.services.parcels import ParcelService
from subphora.services.section import SectionService
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
_NATIONAL_STATUS = {
    NationalFailure.NOT_BUILT: 404,
    NationalFailure.OUTSIDE_BUILT_AREA: 404,
    NationalFailure.UNKNOWN_LAYER: 404,
    NationalFailure.INVALID_TILE: 400,
    NationalFailure.UNREADABLE: 500,
}
_PARCEL_STATUS = {
    ParcelFailure.INVALID_AREA: 400,
    ParcelFailure.TOO_LARGE: 422,
    ParcelFailure.OUTSIDE_COVERAGE: 422,
    ParcelFailure.UNKNOWN_JOB: 404,
    ParcelFailure.NOT_READY: 409,
    ParcelFailure.OUTSIDE_GRID: 404,
    ParcelFailure.UNKNOWN_LAYER: 404,
    ParcelFailure.UNREADABLE: 500,
}
_SECTION_STATUS = {
    SectionFailure.INVALID_LINE: 400,
    SectionFailure.TOO_SHORT: 422,
    SectionFailure.TOO_LONG: 422,
    SectionFailure.OUTSIDE_TERRITORY: 422,
    SectionFailure.OUTSIDE_COVERAGE: 422,
    SectionFailure.UPSTREAM_ERROR: 502,
    SectionFailure.UPSTREAM_TIMEOUT: 504,
}
_FIELD_STATUS = {
    FieldFailure.INVALID_OBSERVATION: 400,
    FieldFailure.TOO_MANY: 413,
    FieldFailure.NOTE_TOO_LONG: 422,
    FieldFailure.UNKNOWN_OBSERVATION: 404,
    FieldFailure.NO_MEDIA: 422,
    FieldFailure.MEDIA_TYPE: 415,
    FieldFailure.MEDIA_TOO_LARGE: 413,
    FieldFailure.MEDIA_MISMATCH: 400,
    FieldFailure.STORE_UNAVAILABLE: 503,
}
_AREA_ID = fastapi.Path(pattern=r"^[0-9a-f]{16}$")
_OBSERVATION_ID = fastapi.Path(
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_PNG = "image/png"
_ZOOM = Query(ge=0, le=MAX_TILE_ZOOM)
_TILE_INDEX = fastapi.Path(ge=0)


class DrawnPolygon(DomainModel):
    """The body of ``POST /api/aoi/polygon``: a GeoJSON Polygon of one ring, no holes."""

    type: Literal["Polygon"]
    coordinates: tuple[tuple[Position, ...]] = Field(min_length=1, max_length=1)


class FieldBatch(DomainModel):
    """The body of ``POST /api/field/observations``: the outbox's next records."""

    observations: tuple[Observation, ...] = Field(min_length=1)


class DrawnLine(DomainModel):
    """The body of ``POST /api/section``: a straight line's two ends, in degrees."""

    start: Position
    end: Position


def create_app(
    settings: Settings,
    root: Path = REPO_ROOT,
    transport: Transport | None = None,
    executor: Executor | None = None,
) -> FastAPI:
    """The application; ``transport`` replaces the network and ``executor`` the worker
    processes of the detailed maps in tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            # One client for the life of the server: its per-host limits hold across requests.
            client = await stack.enter_async_context(
                CatalogueClient(settings.sources, __version__, transport)
            )
            workers = executor or stack.enter_context(
                ProcessPoolExecutor(max_workers=settings.parcel.jobs.workers)
            )
            cache = FileCache(settings.store.cache_path(root))
            parcels = ParcelService(client, settings.sources, cache)
            app.state.aoi = AoiService(client, settings, cache, parcels)
            app.state.areas = AreaService(client, settings, cache)
            app.state.layers = LayerService(client, settings, cache, app.state.areas)
            app.state.national = NationalMapService(settings, root)
            app.state.legal = LegalService(app.state.layers, settings)
            app.state.parcel = ParcelMapService(
                client, settings, cache, root, workers, app.state.legal
            )
            app.state.section = SectionService(client, settings, cache, root)
            app.state.field = FieldService(settings, root)
            stack.callback(app.state.national.close)
            stack.push_async_callback(app.state.parcel.close)
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

    @app.exception_handler(NationalError)
    async def national_failed(_request: Request, exc: NationalError) -> JSONResponse:
        if exc.failure is NationalFailure.UNREADABLE:
            _log.error("the national map cannot be read: %s", exc.detail)
        return JSONResponse(
            status_code=_NATIONAL_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    @app.exception_handler(ParcelError)
    async def parcel_failed(_request: Request, exc: ParcelError) -> JSONResponse:
        if exc.failure is ParcelFailure.UNREADABLE:
            _log.error("a detailed map cannot be read: %s", exc.detail)
        return JSONResponse(
            status_code=_PARCEL_STATUS[exc.failure],
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

    def national(request: Request) -> NationalMapService:
        service: NationalMapService = request.app.state.national
        return service

    @app.get("/api/national")
    async def national_layers(request: Request) -> NationalMap:
        return national_map(settings, await national(request).describe())

    @app.get("/api/national/tiles/{layer_id}/{z}/{x}/{y}", response_class=Response)
    async def national_tile(
        layer_id: str,
        z: Annotated[int, _TILE_INDEX],
        x: Annotated[int, _TILE_INDEX],
        y: Annotated[int, _TILE_INDEX],
        request: Request,
    ) -> Response:
        content = await national(request).tile(layer_id, z, x, y)
        max_age = settings.national.tiles.browser_cache_s
        return Response(
            content=content,
            media_type=_PNG,
            headers={"Cache-Control": f"public, max-age={max_age}"},
        )

    @app.get("/api/national/explain")
    async def national_explain(
        lon: Annotated[float, Query(ge=-180, le=180)],
        lat: Annotated[float, Query(ge=-85, le=85)],
        request: Request,
    ) -> CellExplanation:
        return await national(request).explain(lon, lat)

    def parcel(request: Request) -> ParcelMapService:
        service: ParcelMapService = request.app.state.parcel
        return service

    @app.post("/api/parcel")
    async def parcel_start(request: Request, response: Response) -> ParcelAnswer:
        try:
            area = AreaOfInterest.model_validate_json(await request.body())
        except ValidationError as exc:
            raise ParcelError(
                ParcelFailure.INVALID_AREA, "the body is not an area of interest"
            ) from exc
        job = await parcel(request).submit(area)
        if job.state in (JobState.QUEUED, JobState.RUNNING):
            response.status_code = 202
        return parcel_answer(settings, job)

    @app.get("/api/parcel/{area_id}")
    async def parcel_job(area_id: Annotated[str, _AREA_ID], request: Request) -> ParcelAnswer:
        return parcel_answer(settings, await parcel(request).job(area_id))

    @app.get("/api/parcel/{area_id}/explain")
    async def parcel_explain(
        area_id: Annotated[str, _AREA_ID],
        lon: Annotated[float, Query(ge=-180, le=180)],
        lat: Annotated[float, Query(ge=-85, le=85)],
        request: Request,
    ) -> ParcelExplanation:
        return await parcel(request).explain(area_id, lon, lat)

    @app.get("/api/parcel/{area_id}/layers/{layer_id}", response_class=Response)
    async def parcel_layer(
        area_id: Annotated[str, _AREA_ID], layer_id: str, request: Request
    ) -> Response:
        content = await parcel(request).image(area_id, layer_id)
        # An area's id changes with its settings and code: its images never change.
        return Response(
            content=content, media_type=_PNG, headers={"Cache-Control": "private, max-age=86400"}
        )

    @app.exception_handler(SectionError)
    async def section_failed(_request: Request, exc: SectionError) -> JSONResponse:
        if exc.failure in (SectionFailure.UPSTREAM_ERROR, SectionFailure.UPSTREAM_TIMEOUT):
            _log.warning("a section failed upstream: %s", exc.detail)
        return JSONResponse(
            status_code=_SECTION_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    @app.get("/api/legal")
    async def legal(
        lon: Annotated[float, Query(ge=-180, le=180)],
        lat: Annotated[float, Query(ge=-85, le=85)],
        region: Annotated[str, Query(pattern=r"^[A-Z]{2}-[A-Z]{2}$")],
        request: Request,
    ) -> LegalStatus:
        service: LegalService = request.app.state.legal
        return await service.place(lon, lat, region)

    @app.post("/api/section")
    async def section(request: Request) -> CrossSection:
        try:
            line = DrawnLine.model_validate_json(await request.body())
        except ValidationError as exc:
            raise SectionError(SectionFailure.INVALID_LINE, "the body is not a line") from exc
        for lon, lat in (line.start, line.end):
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise SectionError(SectionFailure.INVALID_LINE, "an end is not in degrees")
        service: SectionService = request.app.state.section
        return await service.section(line.start, line.end)

    @app.exception_handler(FieldError)
    async def field_failed(_request: Request, exc: FieldError) -> JSONResponse:
        if exc.failure is FieldFailure.STORE_UNAVAILABLE:
            _log.error("the field store failed: %s", exc.detail)
        return JSONResponse(
            status_code=_FIELD_STATUS[exc.failure],
            content={"code": exc.failure.value, "detail": exc.detail},
        )

    def field(request: Request) -> FieldService:
        service: FieldService = request.app.state.field
        return service

    @app.post("/api/field/observations")
    async def field_sync(request: Request) -> SyncAnswer:
        try:
            batch = FieldBatch.model_validate_json(await request.body())
        except ValidationError as exc:
            # Where the batch is wrong, never what it holds (a record may be private).
            where = ".".join(str(part) for part in exc.errors()[0]["loc"])
            raise FieldError(
                FieldFailure.INVALID_OBSERVATION, f"the batch is not valid at {where or 'root'}"
            ) from exc
        return SyncAnswer(results=await field(request).sync(batch.observations))

    @app.put("/api/field/observations/{observation_id}/media")
    async def field_media(
        observation_id: Annotated[str, _OBSERVATION_ID], request: Request, response: Response
    ) -> MediaAnswer:
        limit = settings.field.media.max_bytes
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise FieldError(FieldFailure.MEDIA_TOO_LARGE, f"a file has at most {limit} bytes")
        content_type = request.headers.get("content-type", "")
        content = bytearray()
        async for chunk in request.stream():
            content += chunk
            if len(content) > limit:
                raise FieldError(FieldFailure.MEDIA_TOO_LARGE, f"a file has at most {limit} bytes")
        outcome = await field(request).media(observation_id, content_type, bytes(content))
        if outcome is Outcome.CREATED:
            response.status_code = 201
        return MediaAnswer(id=observation_id, outcome=outcome)

    @app.get("/api/areas/{area_id}")
    async def area(area_id: str, request: Request, response: Response) -> AreaBoundary:
        areas: AreaService = request.app.state.areas
        boundary = await areas.boundary(area_id)
        # The browser may keep it as long as the server's cache does.
        lifetime = settings.sources.service(boundary.source.service_id).politeness
        response.headers["Cache-Control"] = f"public, max-age={lifetime.cache_lifetime_s}"
        return boundary

    return app
