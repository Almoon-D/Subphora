# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The HTTP API: ``create_app(settings)``, served by ``subphora serve``.

- ``GET /api/parcels/{reference}``: a cadastral parcel (outline in EPSG:4326, area,
  municipality, province), or an error whose ``code`` says why there is none.
- ``GET /api/map``: the base map and the cadastral overlay the front end draws, built from
  the source catalogue so that no host or attribution is written in the front end.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from subphora import __version__
from subphora.api.map import MapConfig, map_config
from subphora.config import REPO_ROOT, Settings
from subphora.domain.parcels import CadastralParcel, LookupFailure, ParcelLookupError
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

    @app.get("/api/parcels/{reference}")
    async def parcel(reference: str, request: Request) -> CadastralParcel:
        service: ParcelService = request.app.state.parcels
        return await service.lookup(reference)

    @app.get("/api/map")
    async def map_layers() -> MapConfig:
        return map_body

    return app
