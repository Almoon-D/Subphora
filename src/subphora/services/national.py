# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The national build (``subphora national build``): download the nationwide inputs of each
region politely, compute its grids in a worker process, then render the map's tiles.

- A region is a province (ISO 3166-2, ES-Z), every province of a region (ES-AR), or a box
  in degrees; ``--all`` is every province. Each is computed on its grid (the mainland's or
  the Canaries') over its box plus a buffer, then clipped to its official boundary.
- Every download goes through the catalogue client (its per-host limits) and the file
  cache, so a second build reads what is still fresh from ``data/cache``.
- A region whose download fails is reported and skipped; the others are still built, and
  the tiles cover every region on disk.
"""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from subphora.config import Settings
from subphora.config.national import GridSettings
from subphora.config.sources import Service
from subphora.countries.es.areas import all_provinces, ign_province_code, provinces_of
from subphora.domain.potential import InputSource
from subphora.geo.grid import (
    Bounds,
    GridWindow,
    buffered,
    geometry_bounds,
    transform_bounds,
    window_around,
)
from subphora.geo.tiles import tiles_covering
from subphora.model.quality import ground_resolution_m
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure
from subphora.services.national_compute import (
    RegionInputs,
    RegionJob,
    RegionResult,
    TileJob,
    compute_region,
    render_tiles,
)
from subphora.sources import CatalogueClient
from subphora.sources.boundaries import BoundaryParseError, boundary_params, parse_boundary
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
from subphora.store.national import (
    MapManifest,
    RegionSummary,
    map_path,
    read_manifests,
    tiles_path,
    write_json,
    write_tiles,
)

_log = logging.getLogger(__name__)

_LON_LAT = "EPSG:4326"
# A paged query that keeps saying "more" past this many pages is refused, not followed.
_MAX_PAGES = 2000
# Tiles per worker job.
_TILE_BATCH = 64


class RegionSpecError(ValueError):
    """A ``--region`` that names no province, region or box in Spain."""


@dataclass(frozen=True, slots=True)
class BuildRegion:
    id: str
    name: str
    grid: GridSettings
    # The IGN administrative-unit code of a province; None for a box.
    boundary_code: str | None
    # A box region's bounds in degrees; a province's come from its boundary.
    bbox: Bounds | None = None


@dataclass(frozen=True, slots=True)
class RegionFailure:
    region_id: str
    detail: str


@dataclass(frozen=True, slots=True)
class BuildReport:
    built: list[RegionResult]
    failed: list[RegionFailure]
    # Tiles written per layer.
    tiles: dict[str, int]


class BuildFailure(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _province_regions(settings: Settings, area: str) -> list[BuildRegion]:
    return [
        BuildRegion(
            id=province.iso,
            name=province.name,
            grid=settings.national.grid_of_region(province.region),
            boundary_code=ign_province_code(province),
        )
        for province in provinces_of(area)
    ]


def all_regions(settings: Settings) -> list[BuildRegion]:
    return [r for p in all_provinces() for r in _province_regions(settings, p.iso)]


def resolve_region(settings: Settings, spec: str) -> list[BuildRegion]:
    """The build regions of a province or region code, or of a box ``west,south,east,north``
    in degrees that lies in one territory; raises RegionSpecError."""
    regions = _province_regions(settings, spec.strip().upper())
    if regions:
        return regions
    parts = spec.split(",")
    if len(parts) != 4:
        raise RegionSpecError(f"{spec!r} is neither an ISO province or region code nor a box")
    try:
        west, south, east, north = (float(part) for part in parts)
    except ValueError:
        raise RegionSpecError(f"{spec!r}: a box is four numbers in degrees") from None
    if not (west < east and south < north) or not all(
        math.isfinite(v) for v in (west, south, east, north)
    ):
        raise RegionSpecError(f"{spec!r}: a box is west,south,east,north")
    for territory in settings.search.territories:
        t_west, t_south, t_east, t_north = territory.bbox
        if t_west <= west and east <= t_east and t_south <= south and north <= t_north:
            grid = next(g for g in settings.national.grids if territory.id in g.territories)
            box_id = f"box{west:+.3f}{south:+.3f}{east:+.3f}{north:+.3f}"
            return [
                BuildRegion(
                    id=box_id,
                    name=box_id,
                    grid=grid,
                    boundary_code=None,
                    bbox=(west, south, east, north),
                )
            ]
    raise RegionSpecError(f"{spec!r} does not lie within one territory of Spain")


def _oldest(fetched: Sequence[Fetched]) -> datetime | None:
    return min((f.provenance.retrieved_at for f in fetched), default=None)


class NationalBuilder:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        root: Path,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._settings = settings
        self._national = settings.national
        self._root = root
        self._clock = clock

    @property
    def output(self) -> Path:
        return self._national.build.output_path(self._root)

    def _service(self, service_id: str) -> Service:
        return self._settings.sources.service(service_id)

    async def _get(
        self, service: Service, url: str, params: Params, check: Callable[[bytes], Any]
    ) -> tuple[Any, Fetched]:
        """Fetch, parse with ``check`` and cache only an answer that parses. A failure the
        service reports as its own is asked again, like a transport error."""
        client = self._settings.sources.client
        attempts = client.retries + 1
        for attempt in range(1, attempts + 1):
            fetched = await self._fetcher.fetch(service, url, params)
            try:
                parsed = check(fetched.content)
            except InputParseError as exc:
                if not exc.transient or attempt == attempts:
                    raise BuildFailure(f"{service.publisher}: {exc}") from exc
                await asyncio.sleep(client.retry_backoff_s * attempt)
                continue
            except BoundaryParseError as exc:
                raise BuildFailure(f"{service.publisher}: {exc}") from exc
            await self._fetcher.store(service, fetched)
            return parsed, fetched
        raise AssertionError("unreachable")  # pragma: no cover

    async def _boundary(self, region: BuildRegion) -> tuple[list[dict[str, Any]], Bounds]:
        source = self._settings.regional.boundaries.sources["region"]
        service = self._service(source.service)
        if region.boundary_code is None:  # pragma: no cover - only provinces have one
            raise BuildFailure(f"{region.id} has no official boundary")
        params = boundary_params(
            source.type_name,
            source.code_property,
            region.boundary_code,
            source.namespaces,
            source.output_format,
        )
        geometries, _ = await self._get(service, service.base_url, params, parse_boundary)
        shapes = [g for g in geometries if isinstance(g, dict)]
        return shapes, geometry_bounds(shapes)

    async def _pages(
        self,
        service: Service,
        url: str,
        params_of: Callable[[int], Params],
        parse: Callable[[bytes], Page],
        page_size: int,
    ) -> tuple[list[dict[str, Any]], list[Fetched]]:
        features: list[dict[str, Any]] = []
        fetched: list[Fetched] = []
        for number in range(_MAX_PAGES):
            page, answer = await self._get(service, url, params_of(number * page_size), parse)
            features.extend(page.features)
            fetched.append(answer)
            if not page.more:
                return features, fetched
        raise BuildFailure(f"{service.publisher}: more than {_MAX_PAGES} pages")

    async def _arcgis(
        self,
        dataset_path: str,
        service_id: str,
        window: GridWindow,
        fields: list[str],
        page_size: int,
        generalise: float | None,
    ) -> tuple[list[dict[str, Any]], list[Fetched]]:
        service = self._service(service_id)
        return await self._pages(
            service,
            service.base_url + dataset_path,
            lambda offset: arcgis_query_params(
                window.bounds, window.crs, fields, offset, page_size, generalise
            ),
            parse_arcgis_page,
            page_size,
        )

    async def _bodies(self, window: GridWindow) -> tuple[list[dict[str, Any]], list[Fetched]]:
        dataset = self._national.datasets.groundwater_bodies
        service = self._service(dataset.service)
        bounds = transform_bounds(window.bounds, window.crs, dataset.srs)
        return await self._pages(
            service,
            service.base_url,
            lambda start: wfs_page_params(
                dataset.type_name,
                dataset.srs,
                bounds,
                dataset.code_field,
                start,
                dataset.page_size,
            ),
            lambda content: parse_wfs_page(content, dataset.page_size),
            dataset.page_size,
        )

    async def _terrain(
        self, grid: GridSettings, window: GridWindow
    ) -> tuple[list[bytes], list[Fetched]]:
        dataset = self._national.datasets.terrain
        service = self._service(dataset.service)
        coverage = grid.terrain
        west, south, east, north = transform_bounds(window.bounds, window.crs, coverage.crs)
        e_west, e_south, e_east, e_north = coverage.extent
        size = dataset.window_m
        boxes = []
        x = math.floor(max(west, e_west) / size) * size
        while x < min(east, e_east):
            y = math.floor(max(south, e_south) / size) * size
            while y < min(north, e_north):
                boxes.append(
                    (
                        max(e_west, x - dataset.overlap_m),
                        max(e_south, y - dataset.overlap_m),
                        min(e_east, x + size + dataset.overlap_m),
                        min(e_north, y + size + dataset.overlap_m),
                    )
                )
                y += size
            x += size
        return await self._rasters(service, [wcs_params(coverage.coverage, box) for box in boxes])

    async def _soil(self, window: GridWindow) -> tuple[list[bytes], list[Fetched]]:
        dataset = self._national.datasets.soil
        service = self._service(dataset.service)
        west, south, east, north = transform_bounds(window.bounds, window.crs, _LON_LAT)
        size = dataset.window_deg
        params = []
        x = math.floor(west / size) * size
        while x < east:
            y = math.floor(south / size) * size
            while y < north:
                params.append(soilgrids_params(dataset.coverage, (x, y, x + size, y + size)))
                y += size
            x += size
        return await self._rasters(service, params)

    async def _rasters(
        self, service: Service, requests: Sequence[Params]
    ) -> tuple[list[bytes], list[Fetched]]:
        answers = await asyncio.gather(
            *(self._get(service, service.base_url, params, check_tiff) for params in requests)
        )
        return [fetched.content for _, fetched in answers], [fetched for _, fetched in answers]

    def _source(self, dataset_name: str, fetched: Sequence[Fetched]) -> InputSource:
        dataset = self._national.datasets.all()[dataset_name]
        service = self._service(dataset.service)
        retrieved = _oldest(fetched) or self._clock()
        return InputSource(
            service_id=service.id,
            publisher=service.publisher,
            attribution=service.attribution,
            retrieved_at=retrieved,
            detail=dataset.detail,
            resolution_m=ground_resolution_m(
                dataset.detail, self._settings.regional.rule.metres_per_scale_unit
            ),
        )

    async def prepare(self, region: BuildRegion) -> RegionJob:
        """Download everything one region needs; raises BuildFailure."""
        try:
            return await self._prepare(region)
        except UpstreamFailure as exc:
            raise BuildFailure(exc.detail) from exc

    async def _prepare(self, region: BuildRegion) -> RegionJob:
        national = self._national
        grid = region.grid
        if region.bbox is not None:
            boundary, bbox = None, region.bbox
        else:
            shapes, bbox = await self._boundary(region)
            boundary = shapes
        bounds = buffered(transform_bounds(bbox, _LON_LAT, grid.crs), national.buffer_m)
        window = window_around(grid.crs, national.resolution_m, bounds)
        datasets = national.datasets
        _log.info(
            "%s: downloading the inputs of %d x %d cells", region.id, window.width, window.height
        )
        permeability, terrain, soil, bodies, points = await asyncio.gather(
            self._arcgis(
                datasets.permeability.path,
                datasets.permeability.service,
                window,
                [datasets.permeability.class_field, datasets.permeability.label_field],
                datasets.permeability.page_size,
                datasets.permeability.generalise_m,
            ),
            self._terrain(grid, window),
            self._soil(window),
            self._bodies(window),
            self._arcgis(
                datasets.water_points.path,
                datasets.water_points.service,
                window,
                [datasets.water_points.kind_field],
                datasets.water_points.page_size,
                None,
            ),
        )
        return RegionJob(
            root=self.output,
            region_id=region.id,
            name=region.name,
            grid_id=grid.id,
            window=window,
            bbox=bbox,
            built_at=self._clock(),
            national=national,
            model=self._settings.model,
            metres_per_scale_unit=self._settings.regional.rule.metres_per_scale_unit,
            sources={
                "permeability": self._source("permeability", permeability[1]),
                "terrain": self._source("terrain", terrain[1]),
                "soil": self._source("soil", soil[1]),
                "groundwater_bodies": self._source("groundwater_bodies", bodies[1]),
                "water_points": self._source("water_points", points[1]),
            },
            inputs=RegionInputs(
                boundary=boundary,
                permeability=permeability[0],
                terrain=terrain[0],
                soil=soil[0],
                groundwater_bodies=bodies[0],
                water_points=points[0],
            ),
        )

    async def build(
        self, regions: Sequence[BuildRegion], executor: Executor, workers: int
    ) -> BuildReport:
        """Every region (its downloads overlapping the computing of the ones before), then
        the tiles over every region on disk."""
        loop = asyncio.get_running_loop()
        in_flight: list[tuple[str, Awaitable[RegionResult]]] = []
        built: list[RegionResult] = []
        failed: list[RegionFailure] = []

        async def settle(region_id: str, result: Awaitable[RegionResult]) -> None:
            try:
                done = await result
            except Exception as exc:  # a worker's failure is reported, not fatal
                _log.exception("%s: computing failed", region_id)
                failed.append(RegionFailure(region_id, f"computing failed: {exc}"))
            else:
                _log.info("%s: %d cells, %d scored", region_id, done.cells, done.scored)
                built.append(done)

        for region in regions:
            try:
                job = await self.prepare(region)
            except BuildFailure as exc:
                _log.warning("%s: %s", region.id, exc.detail)
                failed.append(RegionFailure(region.id, exc.detail))
                continue
            in_flight.append((region.id, loop.run_in_executor(executor, compute_region, job)))
            while len(in_flight) >= max(1, workers):
                await settle(*in_flight.pop(0))
        for region_id, result in in_flight:
            await settle(region_id, result)
        tiles = await self.render(executor) if built else {}
        return BuildReport(built=built, failed=failed, tiles=tiles)

    async def render(self, executor: Executor) -> dict[str, int]:
        """Every layer's tiles over every region on disk, then ``map.json``."""
        root = self.output
        manifests = tuple(await asyncio.to_thread(read_manifests, root))
        if not manifests:
            return {}
        settings = self._national.tiles
        loop = asyncio.get_running_loop()
        bounds = (
            min(m.bbox[0] for m in manifests),
            min(m.bbox[1] for m in manifests),
            max(m.bbox[2] for m in manifests),
            max(m.bbox[3] for m in manifests),
        )
        counts: dict[str, int] = {}
        for layer in settings.layers:
            jobs = []
            for z in range(settings.min_zoom, settings.max_zoom + 1):
                tiles = sorted({(z, x, y) for m in manifests for x, y in tiles_covering(m.bbox, z)})
                for start in range(0, len(tiles), _TILE_BATCH):
                    jobs.append(
                        TileJob(
                            root=root,
                            manifests=manifests,
                            variable=layer.variable,
                            breaks=tuple(layer.breaks),
                            colours=tuple(layer.colours),
                            tile_size=settings.tile_size,
                            tiles=tuple(tiles[start : start + _TILE_BATCH]),
                        )
                    )
            batches = await asyncio.gather(
                *(loop.run_in_executor(executor, render_tiles, job) for job in jobs)
            )
            rendered = [tile for batch in batches for tile in batch]
            metadata = {"name": layer.id, "variable": layer.variable.value, "unit": layer.unit}
            counts[layer.id] = await asyncio.to_thread(
                write_tiles, tiles_path(root, layer.id), rendered, bounds, metadata
            )
            _log.info("%s: %d tiles", layer.id, counts[layer.id])
        summary = MapManifest(
            rendered_at=self._clock(),
            regions=tuple(
                RegionSummary(
                    region_id=m.region_id,
                    name=m.name,
                    grid=m.grid,
                    bbox=m.bbox,
                    built_at=m.built_at,
                )
                for m in manifests
            ),
            bounds=bounds,
            tiles=counts,
        )
        await asyncio.to_thread(write_json, map_path(root), summary)
        return counts


__all__ = [
    "BuildFailure",
    "BuildRegion",
    "BuildReport",
    "NationalBuilder",
    "RegionFailure",
    "RegionSpecError",
    "all_regions",
    "resolve_region",
]
