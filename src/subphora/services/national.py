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
from collections.abc import Awaitable, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subphora.config import Settings
from subphora.config.national import GridSettings
from subphora.countries.es.areas import all_provinces, ign_province_code, provinces_of
from subphora.domain.potential import InputSource
from subphora.geo.grid import (
    Bounds,
    buffered,
    geometry_bounds,
    transform_bounds,
    window_around,
)
from subphora.geo.tiles import tiles_covering
from subphora.services.fetching import Fetched
from subphora.services.inputs import InputFailure, InputFetcher
from subphora.services.national_compute import (
    RegionInputs,
    RegionJob,
    RegionResult,
    TileJob,
    compute_region,
    render_tiles,
)
from subphora.sources import CatalogueClient
from subphora.sources.boundaries import boundary_params, parse_boundary
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


class NationalBuilder:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        root: Path,
        clock: Clock = utc_now,
    ) -> None:
        self._inputs = InputFetcher(client, settings, cache, clock)
        self._settings = settings
        self._national = settings.national
        self._root = root
        self._clock = clock

    @property
    def output(self) -> Path:
        return self._national.build.output_path(self._root)

    async def _boundary(self, region: BuildRegion) -> tuple[list[dict[str, Any]], Bounds]:
        source = self._settings.regional.boundaries.sources["region"]
        service = self._inputs.service(source.service)
        if region.boundary_code is None:  # pragma: no cover - only provinces have one
            raise BuildFailure(f"{region.id} has no official boundary")
        params = boundary_params(
            source.type_name,
            source.code_property,
            region.boundary_code,
            source.namespaces,
            source.output_format,
        )
        geometries, _ = await self._inputs.get(service, service.base_url, params, parse_boundary)
        shapes = [g for g in geometries if isinstance(g, dict)]
        return shapes, geometry_bounds(shapes)

    def _source(self, dataset_name: str, fetched: Sequence[Fetched]) -> InputSource:
        dataset = self._national.datasets.all()[dataset_name]
        return self._inputs.source(dataset.service, dataset.detail, fetched)

    async def prepare(self, region: BuildRegion) -> RegionJob:
        """Download everything one region needs; raises BuildFailure."""
        try:
            return await self._prepare(region)
        except InputFailure as exc:
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
        inputs = self._inputs
        terrain_dataset = datasets.terrain
        permeability, terrain, soil, bodies, points = await asyncio.gather(
            inputs.arcgis(
                datasets.permeability.service,
                datasets.permeability.path,
                window.bounds,
                window.crs,
                [datasets.permeability.class_field, datasets.permeability.label_field],
                datasets.permeability.page_size,
                datasets.permeability.generalise_m,
            ),
            inputs.terrain(
                terrain_dataset.service,
                grid.terrain,
                terrain_dataset.window_m,
                terrain_dataset.overlap_m,
                window.bounds,
                window.crs,
            ),
            inputs.soil(datasets.soil, window.bounds, window.crs),
            inputs.bodies(datasets.groundwater_bodies, window.bounds, window.crs),
            inputs.arcgis(
                datasets.water_points.service,
                datasets.water_points.path,
                window.bounds,
                window.crs,
                [datasets.water_points.kind_field, self._settings.validation.labels.yield_field],
                datasets.water_points.page_size,
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
            validation=self._settings.validation,
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
