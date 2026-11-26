# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The detailed potential map of an area of interest, as a job (MASTER_PLAN §4.3).

- An area's id is a hash of its outline and of every setting and version that shapes its
  map: the same area asked again is the same job, and a cached result is served until the
  settings or the code change.
- A job is refused at once when its window is too large or lies outside the terrain
  coverage. Otherwise it is queued; at most ``jobs.workers`` run at a time. A running job
  downloads its inputs (catalogue client and file cache), then computes in a worker
  process (never in the event loop) and writes its result under ``jobs.output_dir``.
- A failed job says why (an upstream service, or the computing); asking again retries it.
  A finished one is read from disk, so it survives a restart of the server.
- The job reads the national map's validation of the domains near the area and the
  imported piezometric levels; a new national build or a new import changes the area's id,
  so its map is computed again.
"""

import asyncio
import hashlib
import logging
import math
from collections.abc import Awaitable
from concurrent.futures import Executor
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from subphora import __version__
from subphora.config import Settings
from subphora.config.national import TerrainCoverage
from subphora.domain.aoi import AreaOfInterest, PointGeometry
from subphora.domain.parcel_map import (
    AreaAnalysis,
    JobState,
    ParcelError,
    ParcelExplanation,
    ParcelFailure,
    ParcelJob,
)
from subphora.domain.validation import MEASURED, DomainValidation
from subphora.geo.grid import (
    Bounds,
    GridWindow,
    buffered,
    geometry_bounds,
    transform_bounds,
    transform_geometry,
    transform_xy,
    window_around,
)
from subphora.geo.raster import Geometry
from subphora.geo.render import transparent_png
from subphora.services.fetching import Fetched
from subphora.services.inputs import Features, InputFailure, InputFetcher
from subphora.services.legal import LegalService
from subphora.services.national_map import estimate_at
from subphora.services.parcel_compute import ParcelInputs, ParcelJobSpec, compute_parcel
from subphora.services.piezometry import piezometer_points
from subphora.sources import CatalogueClient
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now
from subphora.store.national import map_path, read_manifest, read_manifests
from subphora.store.parcels import image_path, read_analysis, write_analysis
from subphora.store.piezometry import read_piezometry

_log = logging.getLogger(__name__)

_LON_LAT = "EPSG:4326"
# Vertices of the disc analysed around a point.
_DISC_VERTICES = 64
_ID_LENGTH = 16


@dataclass(frozen=True, slots=True)
class AreaPlan:
    """Where and how an area's grid lies, before anything is downloaded."""

    area_id: str
    label: str | None
    area: list[Geometry]
    area_m2: float
    area_bounds: Bounds
    window: GridWindow
    coverage: TerrainCoverage
    # The region (ISO 3166-2) the search placed the area in: its water law applies.
    region: str


@dataclass(slots=True)
class _Job:
    state: JobState
    failure: ParcelFailure | None = None
    detail: str | None = None
    analysis: AreaAnalysis | None = None
    task: asyncio.Task[None] | None = None


def _disc(x: float, y: float, radius: float) -> Geometry:
    ring = [
        [
            x + radius * math.cos(2 * math.pi * k / _DISC_VERTICES),
            y + radius * math.sin(2 * math.pi * k / _DISC_VERTICES),
        ]
        for k in range(_DISC_VERTICES)
    ]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _rank(validation: DomainValidation) -> tuple[bool, int]:
    return (validation.state in MEASURED, validation.productive)


def _ring_area(ring: list[list[float]]) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairwise(ring)) / 2)


class ParcelMapService:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        root: Path,
        executor: Executor,
        legal: LegalService,
        clock: Clock = utc_now,
    ) -> None:
        self._inputs = InputFetcher(client, settings, cache, clock)
        self._legal = legal
        self._settings = settings
        self._parcel = settings.parcel
        self._root = settings.parcel.jobs.output_path(root)
        self._national_root = settings.national.build.output_path(root)
        self._levels_path = settings.piezometry.output_path(root)
        self._executor = executor
        self._clock = clock
        self._jobs: dict[str, _Job] = {}
        self._slots = asyncio.Semaphore(settings.parcel.jobs.workers)
        self._fingerprint = "|".join(
            (
                __version__,
                settings.parcel.model_dump_json(),
                settings.model.model_dump_json(),
                settings.legal.model_dump_json(),
                settings.national.datasets.model_dump_json(),
                settings.piezometry.model_dump_json(),
                settings.drilling.model_dump_json(),
            )
        )

    @property
    def root(self) -> Path:
        return self._root

    async def close(self) -> None:
        """Stop the jobs still running (they are asked again after a restart)."""
        tasks = [job.task for job in self._jobs.values() if job.task and not job.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _data_stamp(self) -> str:
        """When the national map was rendered and the levels imported, as file times."""
        stamps = []
        for path in (map_path(self._national_root), self._levels_path):
            try:
                stamps.append(str(path.stat().st_mtime_ns))
            except FileNotFoundError:
                stamps.append("-")
        return ",".join(stamps)

    def area_id(self, area: AreaOfInterest) -> str:
        content = f"{self._fingerprint}|{self._data_stamp()}|{area.geometry.model_dump_json()}"
        return hashlib.sha256(content.encode()).hexdigest()[:_ID_LENGTH]

    def plan(self, area: AreaOfInterest) -> AreaPlan:
        """The area's grid in its local CRS; raises ParcelError when it is too large or
        outside the terrain coverage."""
        parcel = self._parcel
        crs = area.centre_local.crs
        if isinstance(area.geometry, PointGeometry):
            lon, lat = area.geometry.coordinates
            x, y = transform_xy(lon, lat, _LON_LAT, crs)
            disc = _disc(x, y, parcel.point_radius_m)
            shapes = [disc]
            area_m2 = _ring_area(disc["coordinates"][0])
        else:
            shapes = [
                transform_geometry(
                    {"type": "Polygon", "coordinates": [list(map(list, r)) for r in polygon]},
                    _LON_LAT,
                    crs,
                )
                for polygon in area.geometry.coordinates
            ]
            area_m2 = area.area_m2 or sum(_ring_area(s["coordinates"][0]) for s in shapes)
        bounds = geometry_bounds(shapes)
        window = window_around(crs, parcel.resolution_m, buffered(bounds, parcel.buffer_m))
        cells = window.width * window.height
        if cells > parcel.max_cells:
            raise ParcelError(
                ParcelFailure.TOO_LARGE,
                f"the area needs {cells} cells of {parcel.resolution_m:g} m with its buffer; "
                f"the most is {parcel.max_cells}",
            )
        grid = self._settings.national.grid_of_region(area.region_code)
        coverage = parcel.terrain.coverages[grid.id]
        west, south, east, north = transform_bounds(bounds, crs, coverage.crs)
        c_west, c_south, c_east, c_north = coverage.extent
        if not (west < c_east and c_west < east and south < c_north and c_south < north):
            raise ParcelError(
                ParcelFailure.OUTSIDE_COVERAGE,
                f"the area lies outside the terrain coverage {coverage.coverage}",
            )
        return AreaPlan(
            area_id=self.area_id(area),
            label=area.label,
            area=shapes,
            area_m2=area_m2,
            area_bounds=bounds,
            window=window,
            coverage=coverage,
            region=area.region_code,
        )

    def _answer(self, area_id: str, job: _Job) -> ParcelJob:
        return ParcelJob(
            id=area_id,
            state=job.state,
            failure=job.failure,
            detail=job.detail,
            poll_after_s=self._parcel.jobs.poll_after_s,
            analysis=job.analysis,
        )

    async def _finished(self, area_id: str) -> AreaAnalysis | None:
        try:
            return await asyncio.to_thread(read_analysis, self._root, area_id)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc

    async def submit(self, area: AreaOfInterest) -> ParcelJob:
        """The area's job: its finished result, the one queued or running, or a new one."""
        plan = self.plan(area)
        area_id = plan.area_id
        job = self._jobs.get(area_id)
        if job is not None and job.state in (JobState.QUEUED, JobState.RUNNING, JobState.DONE):
            return self._answer(area_id, job)
        finished = await self._finished(area_id)
        if finished is not None:
            job = _Job(state=JobState.DONE, analysis=finished)
        else:
            job = _Job(state=JobState.QUEUED)
            job.task = asyncio.create_task(self._run(plan, job))
        self._jobs[area_id] = job
        return self._answer(area_id, job)

    async def job(self, area_id: str) -> ParcelJob:
        job = self._jobs.get(area_id)
        if job is None:
            finished = await self._finished(area_id)
            if finished is None:
                raise ParcelError(ParcelFailure.UNKNOWN_JOB, f"no job {area_id!r}")
            job = _Job(state=JobState.DONE, analysis=finished)
            self._jobs[area_id] = job
        return self._answer(area_id, job)

    async def _run(self, plan: AreaPlan, job: _Job) -> None:
        async with self._slots:
            job.state = JobState.RUNNING
            try:
                spec = await self._prepare(plan)
                loop = asyncio.get_running_loop()
                analysis = await loop.run_in_executor(self._executor, compute_parcel, spec)
                analysis = await self._assessed(analysis, plan.region)
            except InputFailure as exc:
                _log.warning("area %s: %s", plan.area_id, exc.detail)
                job.state = JobState.FAILED
                job.failure = (
                    ParcelFailure.UPSTREAM_TIMEOUT if exc.timeout else ParcelFailure.UPSTREAM_ERROR
                )
                job.detail = exc.detail
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a worker's failure is reported, not fatal
                _log.exception("area %s: computing failed", plan.area_id)
                job.state = JobState.FAILED
                job.failure = ParcelFailure.COMPUTING_FAILED
                job.detail = f"computing failed: {exc}"
            else:
                job.state = JobState.DONE
                job.analysis = analysis

    async def _assessed(self, analysis: AreaAnalysis, region: str) -> AreaAnalysis:
        """The analysis with its candidates' legal status, written over the computed one.
        A failure of the filter itself leaves them "not evaluated", never the map lost."""
        try:
            assessed = await self._legal.candidates(analysis, region)
        except Exception:  # the map stands without its legal status
            _log.exception("area %s: the legal filter failed", analysis.id)
            return analysis
        await asyncio.to_thread(write_analysis, self._root, assessed)
        return assessed

    async def _prepare(self, plan: AreaPlan) -> ParcelJobSpec:
        """Download everything the area needs; raises InputFailure."""
        inputs = self._inputs
        national = self._settings.national.datasets
        parcel = self._parcel
        window = plan.window
        crs = window.crs
        area_bounds = plan.area_bounds

        def arcgis(
            service: str, path: str, bounds: Bounds, fields: list[str], page_size: int
        ) -> Awaitable[tuple[Features, list[Fetched]]]:
            return inputs.arcgis(service, path, bounds, crs, fields, page_size)

        features = asyncio.gather(
            inputs.arcgis(
                national.permeability.service,
                national.permeability.path,
                window.bounds,
                crs,
                [national.permeability.class_field, national.permeability.label_field],
                national.permeability.page_size,
                national.permeability.generalise_m,
            ),
            inputs.bodies(national.groundwater_bodies, window.bounds, crs),
            arcgis(
                national.water_points.service,
                national.water_points.path,
                buffered(area_bounds, parcel.water_points_radius_m),
                [national.water_points.kind_field],
                national.water_points.page_size,
            ),
            arcgis(
                parcel.faults.service,
                parcel.faults.path,
                window.bounds,
                [parcel.faults.type_field],
                parcel.faults.page_size,
            ),
            arcgis(
                parcel.bedding.service,
                parcel.bedding.path,
                buffered(area_bounds, parcel.bedding.max_distance_m),
                [parcel.bedding.kind_field, parcel.bedding.dip_field],
                parcel.bedding.page_size,
            ),
        )
        rasters = asyncio.gather(
            inputs.terrain(
                parcel.terrain.service,
                plan.coverage,
                parcel.terrain.window_m,
                parcel.terrain.overlap_m,
                window.bounds,
                crs,
            ),
            inputs.soil(national.soil, window.bounds, crs),
        )
        (permeability, bodies, points, faults, bedding), (terrain, soil) = await asyncio.gather(
            features, rasters
        )
        validations = await asyncio.to_thread(self._validations, area_bounds, crs)
        levels = await asyncio.to_thread(read_piezometry, self._levels_path)
        reach = self._settings.piezometry.water_table.max_distance_m
        piezometers = (
            []
            if levels is None
            else await asyncio.to_thread(piezometer_points, levels, crs, area_bounds, reach)
        )
        sources = {
            "permeability": inputs.source(
                national.permeability.service, national.permeability.detail, permeability[1]
            ),
            "terrain": inputs.source(parcel.terrain.service, parcel.terrain.detail, terrain[1]),
            "soil": inputs.source(national.soil.service, national.soil.detail, soil[1]),
            "groundwater_bodies": inputs.source(
                national.groundwater_bodies.service, national.groundwater_bodies.detail, bodies[1]
            ),
            "water_points": inputs.source(
                national.water_points.service, national.water_points.detail, points[1]
            ),
            "faults": inputs.source(parcel.faults.service, parcel.faults.detail, faults[1]),
            "bedding": inputs.source(parcel.bedding.service, parcel.bedding.detail, bedding[1]),
        }
        return ParcelJobSpec(
            root=self._root,
            area_id=plan.area_id,
            label=plan.label,
            area=plan.area,
            area_m2=plan.area_m2,
            window=window,
            built_at=self._clock(),
            parcel=parcel,
            national=self._settings.national,
            model=self._settings.model,
            piezometry=self._settings.piezometry,
            drilling=self._settings.drilling,
            legal=self._settings.legal.texts,
            metres_per_scale_unit=self._settings.regional.rule.metres_per_scale_unit,
            sources=sources,
            validations=validations,
            piezometers=piezometers,
            levels=None if levels is None else levels.source_map(),
            inputs=ParcelInputs(
                permeability=permeability[0],
                terrain=terrain[0],
                soil=soil[0],
                groundwater_bodies=bodies[0],
                water_points=points[0],
                faults=faults[0],
                bedding=bedding[0],
            ),
        )

    def _validations(self, bounds: Bounds, crs: str) -> dict[str, DomainValidation]:
        """Per domain, the national map's validation from the regions that overlap the
        area: a measured one before an unmeasured one, then the most productive wells.
        Blocks; an unreadable national map counts as none (its domains: not validated)."""
        west, south, east, north = transform_bounds(bounds, crs, _LON_LAT)
        try:
            manifests = read_manifests(self._national_root)
        except ValueError:
            _log.warning("the national map cannot be read: its validation is not used")
            return {}
        best: dict[str, DomainValidation] = {}
        for manifest in manifests:
            m_west, m_south, m_east, m_north = manifest.bbox
            if not (m_west < east and west < m_east and m_south < north and south < m_north):
                continue
            for validation in manifest.validation:
                held = best.get(validation.domain)
                if held is None or _rank(validation) > _rank(held):
                    best[validation.domain] = validation
        return best

    async def _done(self, area_id: str) -> AreaAnalysis:
        job = await self.job(area_id)
        if job.analysis is None:
            raise ParcelError(ParcelFailure.NOT_READY, f"the job {area_id} is {job.state}")
        return job.analysis

    async def explain(self, area_id: str, lon: float, lat: float) -> ParcelExplanation:
        analysis = await self._done(area_id)
        try:
            manifest = await asyncio.to_thread(read_manifest, self._root, area_id)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc
        if manifest is None:
            raise ParcelError(ParcelFailure.UNREADABLE, f"the grid of {area_id} is missing")
        estimate = await asyncio.to_thread(estimate_at, self._root, manifest, lon, lat)
        if estimate is None:
            raise ParcelError(ParcelFailure.OUTSIDE_GRID, "the point lies outside the area")
        return ParcelExplanation(
            longitude=lon,
            latitude=lat,
            area_id=area_id,
            cell_m=analysis.cell_m,
            built_at=analysis.built_at,
            estimate=estimate,
        )

    async def image(self, area_id: str, layer_id: str) -> bytes:
        """A layer's image; a transparent pixel when the layer has no value in the area."""
        if layer_id not in self._parcel.layers:
            raise ParcelError(ParcelFailure.UNKNOWN_LAYER, f"no layer {layer_id!r}")
        await self._done(area_id)
        path = image_path(self._root, area_id, layer_id)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            return transparent_png(1)


__all__ = ["AreaPlan", "ParcelMapService"]
