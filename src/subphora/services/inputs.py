# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Downloading the model's inputs over a box, for the national build and the detailed map
of an area alike (docs/knowledge/nationwide-inputs.md).

Every request goes through the catalogue client (its per-host limits) and the file cache,
and an answer is cached only once it parses. A failure a service reports as its own (IGME's
"Failed to execute query") is asked again like a transport error; one that persists, or an
answer that is not the data asked for, raises InputFailure.
"""

import asyncio
import math
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from subphora.config import Settings
from subphora.config.national import GroundwaterBodiesDataset, SoilDataset, TerrainCoverage
from subphora.config.sources import Service
from subphora.domain.layers import LayerDetail
from subphora.domain.potential import InputSource
from subphora.geo.grid import Bounds, transform_bounds
from subphora.model.quality import ground_resolution_m
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure, provenance
from subphora.sources import CatalogueClient
from subphora.sources.boundaries import BoundaryParseError
from subphora.sources.client import Params
from subphora.sources.national import (
    InputParseError,
    Page,
    arcgis_query_params,
    check_tiff,
    parse_arcgis_page,
    parse_wfs_page,
    soilgrids_params,
    wcs_params,
    wfs_page_params,
)
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now

_LON_LAT = "EPSG:4326"
# A paged query that keeps saying "more" past this many pages is refused, not followed.
_MAX_PAGES = 2000

type Features = list[dict[str, Any]]


class InputFailure(Exception):
    """An input could not be downloaded; ``timeout`` tells a slow service from a broken one."""

    def __init__(self, detail: str, *, timeout: bool = False) -> None:
        super().__init__(detail)
        self.detail = detail
        self.timeout = timeout


def oldest(fetched: Sequence[Fetched]) -> datetime | None:
    return min((f.provenance.retrieved_at for f in fetched), default=None)


class InputFetcher:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._settings = settings
        self._clock = clock

    def service(self, service_id: str) -> Service:
        return self._settings.sources.service(service_id)

    async def get(
        self, service: Service, url: str, params: Params, check: Callable[[bytes], Any]
    ) -> tuple[Any, Fetched]:
        """Fetch, parse with ``check`` and cache only an answer that parses."""
        client = self._settings.sources.client
        attempts = client.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                fetched = await self._fetcher.fetch(service, url, params)
            except UpstreamFailure as exc:
                raise InputFailure(exc.detail, timeout=exc.timeout) from exc
            try:
                parsed = check(fetched.content)
            except InputParseError as exc:
                if not exc.transient or attempt == attempts:
                    raise InputFailure(f"{service.publisher}: {exc}") from exc
                await asyncio.sleep(client.retry_backoff_s * attempt)
                continue
            except BoundaryParseError as exc:
                raise InputFailure(f"{service.publisher}: {exc}") from exc
            await self._fetcher.store(service, fetched)
            return parsed, fetched
        raise AssertionError("unreachable")  # pragma: no cover

    async def pages(
        self,
        service: Service,
        url: str,
        params_of: Callable[[int], Params],
        parse: Callable[[bytes], Page],
        page_size: int,
    ) -> tuple[Features, list[Fetched]]:
        features: Features = []
        fetched: list[Fetched] = []
        for number in range(_MAX_PAGES):
            page, answer = await self.get(service, url, params_of(number * page_size), parse)
            features.extend(page.features)
            fetched.append(answer)
            if not page.more:
                return features, fetched
        raise InputFailure(f"{service.publisher}: more than {_MAX_PAGES} pages")

    async def arcgis(
        self,
        service_id: str,
        path: str,
        bounds: Bounds,
        crs: str,
        fields: list[str],
        page_size: int,
        generalise: float | None = None,
    ) -> tuple[Features, list[Fetched]]:
        """The features of an ArcGIS REST layer intersecting ``bounds``, in ``crs``."""
        service = self.service(service_id)
        return await self.pages(
            service,
            service.base_url + path,
            lambda offset: arcgis_query_params(bounds, crs, fields, offset, page_size, generalise),
            parse_arcgis_page,
            page_size,
        )

    async def bodies(
        self, dataset: GroundwaterBodiesDataset, bounds: Bounds, crs: str
    ) -> tuple[Features, list[Fetched]]:
        """The groundwater bodies over ``bounds`` (in ``crs``), in the dataset's ``srs``."""
        service = self.service(dataset.service)
        box = transform_bounds(bounds, crs, dataset.srs)
        return await self.pages(
            service,
            service.base_url,
            lambda start: wfs_page_params(
                dataset.type_name, dataset.srs, box, dataset.code_field, start, dataset.page_size
            ),
            lambda content: parse_wfs_page(content, dataset.page_size),
            dataset.page_size,
        )

    async def terrain(
        self,
        service_id: str,
        coverage: TerrainCoverage,
        window_m: float,
        overlap_m: float,
        bounds: Bounds,
        crs: str,
    ) -> tuple[list[bytes], list[Fetched]]:
        """The coverage over ``bounds`` (in ``crs``) as GeoTIFF windows on a fixed grid of
        ``window_m`` in the coverage's CRS, overlapping by ``overlap_m``, clipped to its
        extent; none where ``bounds`` lies outside it."""
        west, south, east, north = transform_bounds(bounds, crs, coverage.crs)
        e_west, e_south, e_east, e_north = coverage.extent
        boxes = []
        x = math.floor(max(west, e_west) / window_m) * window_m
        while x < min(east, e_east):
            y = math.floor(max(south, e_south) / window_m) * window_m
            while y < min(north, e_north):
                boxes.append(
                    (
                        max(e_west, x - overlap_m),
                        max(e_south, y - overlap_m),
                        min(e_east, x + window_m + overlap_m),
                        min(e_north, y + window_m + overlap_m),
                    )
                )
                y += window_m
            x += window_m
        service = self.service(service_id)
        return await self.rasters(service, [wcs_params(coverage.coverage, box) for box in boxes])

    async def soil(
        self, dataset: SoilDataset, bounds: Bounds, crs: str
    ) -> tuple[list[bytes], list[Fetched]]:
        """SoilGrids over ``bounds`` (in ``crs``) by windows of ``window_deg`` degrees."""
        service = self.service(dataset.service)
        west, south, east, north = transform_bounds(bounds, crs, _LON_LAT)
        size = dataset.window_deg
        params = []
        x = math.floor(west / size) * size
        while x < east:
            y = math.floor(south / size) * size
            while y < north:
                params.append(soilgrids_params(dataset.coverage, (x, y, x + size, y + size)))
                y += size
            x += size
        return await self.rasters(service, params)

    async def rasters(
        self, service: Service, requests: Sequence[Params]
    ) -> tuple[list[bytes], list[Fetched]]:
        answers = await asyncio.gather(
            *(self.get(service, service.base_url, params, check_tiff) for params in requests)
        )
        return [fetched.content for _, fetched in answers], [fetched for _, fetched in answers]

    async def fetch_or_empty(
        self, service: Service, url: str, empty_statuses: Sequence[int]
    ) -> Fetched:
        """A GET whose ``empty_statuses`` mean "nothing here" (an empty body), through the
        cache; ``keep`` caches it once the caller has parsed it. Raises InputFailure."""
        try:
            return await self._fetcher.fetch(service, url, {}, empty_statuses)
        except UpstreamFailure as exc:
            raise InputFailure(exc.detail, timeout=exc.timeout) from exc

    async def keep(self, service: Service, fetched: Fetched) -> None:
        await self._fetcher.store(service, fetched)

    async def recall(self, service: Service, key: str) -> Fetched | None:
        """Something derived from a service's data and kept under ``key``, if fresh."""
        return await self._fetcher.recall(service, key)

    async def remember(self, service: Service, key: str, content: bytes) -> Fetched:
        """Keep something just derived from a service's data, dated now."""
        source = provenance(service, self._clock())
        await self._fetcher.remember(service, key, content, source)
        return Fetched(content, source, key, False)

    def source(
        self, service_id: str, detail: LayerDetail, fetched: Sequence[Fetched]
    ) -> InputSource:
        """Where an input came from: its service, its oldest answer and stated detail."""
        service = self.service(service_id)
        return InputSource(
            service_id=service.id,
            publisher=service.publisher,
            attribution=service.attribution,
            retrieved_at=oldest(fetched) or self._clock(),
            detail=detail,
            resolution_m=ground_resolution_m(
                detail, self._settings.regional.rule.metres_per_scale_unit
            ),
        )


__all__ = ["Features", "InputFailure", "InputFetcher", "oldest"]
