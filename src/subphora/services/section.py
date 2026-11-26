# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The interpretive cross-section under a drawn line (MASTER_PLAN §4.4).

- The line is straight, from its first point to its second, both in one territory of
  ``search.yaml``; it is measured in that place's projected CRS and must lie inside the
  terrain coverage of its national grid.
- Its inputs are downloaded through the catalogue client and the file cache: the detailed
  map's terrain (MDT05) and MAGNA structure (faults, bedding), MAGNA lithology, the
  national water points and groundwater bodies; the imported piezometric levels are read
  from disk. A failing service fails the section and says which.
- The geometry and confidence are the model's (``model.section``), computed off the event
  loop.
"""

import asyncio
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subphora.config import Settings
from subphora.config.search import Territory
from subphora.countries.es import local_crs
from subphora.domain.depth import LevelsSource
from subphora.domain.parcels import Position
from subphora.domain.section import (
    CrossSection,
    FaultCrossing,
    ProfilePoint,
    SectionError,
    SectionFailure,
    SectionGap,
    WaterTablePoint,
)
from subphora.geo.grid import (
    Bounds,
    GridWindow,
    buffered,
    transform_bounds,
    transform_xy,
    window_around,
)
from subphora.geo.raster import FloatGrid, Resampling, burn
from subphora.model import PiezometerPoint, depth_at
from subphora.model.section import (
    BeddingPoint,
    BoreholePoint,
    Line,
    columns_of,
    contacts_of,
    place_bedding,
    select_boreholes,
    surface_units,
)
from subphora.services.inputs import Features, InputFailure, InputFetcher
from subphora.services.national_compute import body_grid, warped
from subphora.services.parcel_compute import line_vertices
from subphora.services.piezometry import piezometer_points
from subphora.sources import CatalogueClient
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now
from subphora.store.piezometry import read_piezometry

_LON_LAT = "EPSG:4326"
# Region code for a grid that lists no regions (local_crs only tells the Canaries apart).
_ANY_REGION = "ES"
_ABSENT = -1


@dataclass(frozen=True, slots=True)
class _Downloaded:
    terrain: list[bytes]
    lithology: Features
    faults: Features
    bedding: Features
    water_points: Features
    bodies: Features


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _sample(grid: FloatGrid, window: GridWindow, x: float, y: float) -> float | None:
    cell = window.cell_of(x, y)
    if cell is None:
        return None
    value = float(grid[cell])
    return None if math.isnan(value) else value


class SectionService:
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
        self._levels_path = settings.piezometry.output_path(root)
        self._clock = clock

    def _territory(self, lon: float, lat: float) -> Territory | None:
        for territory in self._settings.search.territories:
            west, south, east, north = territory.bbox
            if west <= lon <= east and south <= lat <= north:
                return territory
        return None

    def _line(self, start: Position, end: Position) -> tuple[Line, str, str]:
        """The line in its local CRS, and its national grid's id; raises SectionError."""
        first, second = self._territory(*start), self._territory(*end)
        if first is None or second is None or first.id != second.id:
            raise SectionError(
                SectionFailure.OUTSIDE_TERRITORY, "both ends must lie in one territory of Spain"
            )
        national = self._settings.national
        grid = next((g for g in national.grids if first.id in g.territories), national.grids[0])
        region = grid.regions[0] if grid.regions else _ANY_REGION
        crs = local_crs(region, (start[0] + end[0]) / 2)
        x0, y0 = transform_xy(start[0], start[1], _LON_LAT, crs)
        x1, y1 = transform_xy(end[0], end[1], _LON_LAT, crs)
        line = Line(x0, y0, x1, y1)
        section = self._settings.section
        if line.length < section.min_length_m:
            raise SectionError(
                SectionFailure.TOO_SHORT,
                f"the line is {line.length:.0f} m; the least is {section.min_length_m:g} m",
            )
        if line.length > section.max_length_m:
            raise SectionError(
                SectionFailure.TOO_LONG,
                f"the line is {line.length:.0f} m; the most is {section.max_length_m:g} m",
            )
        return line, crs, grid.id

    async def section(self, start: Position, end: Position) -> CrossSection:
        line, crs, grid_id = self._line(start, end)
        settings = self._settings
        parcel, section = settings.parcel, settings.section
        coverage = parcel.terrain.coverages[grid_id]
        box: Bounds = (
            min(line.x0, line.x1),
            min(line.y0, line.y1),
            max(line.x0, line.x1),
            max(line.y0, line.y1),
        )
        west, south, east, north = transform_bounds(box, crs, coverage.crs)
        c_west, c_south, c_east, c_north = coverage.extent
        if not (c_west <= west and east <= c_east and c_south <= south and north <= c_north):
            raise SectionError(
                SectionFailure.OUTSIDE_COVERAGE,
                f"the line leaves the terrain coverage {coverage.coverage}",
            )
        window = window_around(crs, section.sample_m, buffered(box, 2 * section.sample_m))
        try:
            downloaded, sources = await self._download(window, box, crs, coverage)
        except InputFailure as exc:
            failure = (
                SectionFailure.UPSTREAM_TIMEOUT if exc.timeout else SectionFailure.UPSTREAM_ERROR
            )
            raise SectionError(failure, exc.detail) from exc
        levels = await asyncio.to_thread(read_piezometry, self._levels_path)
        reach = settings.piezometry.water_table.max_distance_m
        piezometers = (
            []
            if levels is None
            else await asyncio.to_thread(piezometer_points, levels, crs, box, reach)
        )
        return await asyncio.to_thread(
            self._compute,
            line,
            start,
            end,
            window,
            downloaded,
            sources,
            piezometers,
            None if levels is None else levels.source_map(),
        )

    async def _download(
        self, window: GridWindow, box: Bounds, crs: str, coverage: Any
    ) -> tuple[_Downloaded, dict[str, Any]]:
        inputs = self._inputs
        settings = self._settings
        parcel, section, national = settings.parcel, settings.section, settings.national.datasets
        lithology = section.lithology
        bedding_reach = max(section.dip_max_distance_m, section.confidence.evidence_range_m)
        (
            terrain,
            litho,
            faults,
            bedding,
            points,
            bodies,
        ) = await asyncio.gather(
            inputs.terrain(
                parcel.terrain.service,
                coverage,
                parcel.terrain.window_m,
                parcel.terrain.overlap_m,
                window.bounds,
                crs,
            ),
            inputs.arcgis(
                lithology.service,
                lithology.path,
                buffered(box, lithology.window_m),
                crs,
                [lithology.label_field],
                lithology.page_size,
            ),
            inputs.arcgis(
                parcel.faults.service,
                parcel.faults.path,
                buffered(box, section.confidence.fault_zone_m),
                crs,
                [parcel.faults.type_field],
                parcel.faults.page_size,
            ),
            inputs.arcgis(
                parcel.bedding.service,
                parcel.bedding.path,
                buffered(box, bedding_reach),
                crs,
                [
                    parcel.bedding.kind_field,
                    parcel.bedding.dip_field,
                    section.bedding_direction_field,
                ],
                parcel.bedding.page_size,
            ),
            inputs.arcgis(
                national.water_points.service,
                national.water_points.path,
                buffered(box, section.boreholes.max_distance_m),
                crs,
                [
                    national.water_points.kind_field,
                    section.boreholes.depth_field,
                    section.boreholes.ground_field,
                ],
                national.water_points.page_size,
            ),
            inputs.bodies(national.groundwater_bodies, window.bounds, crs),
        )
        sources = {
            "terrain": inputs.source(parcel.terrain.service, parcel.terrain.detail, terrain[1]),
            "lithology": inputs.source(lithology.service, lithology.detail, litho[1]),
            "faults": inputs.source(parcel.faults.service, parcel.faults.detail, faults[1]),
            "bedding": inputs.source(parcel.bedding.service, parcel.bedding.detail, bedding[1]),
            "boreholes": inputs.source(
                national.water_points.service, national.water_points.detail, points[1]
            ),
            "groundwater_bodies": inputs.source(
                national.groundwater_bodies.service, national.groundwater_bodies.detail, bodies[1]
            ),
        }
        return (
            _Downloaded(
                terrain=terrain[0],
                lithology=litho[0],
                faults=faults[0],
                bedding=bedding[0],
                water_points=points[0],
                bodies=bodies[0],
            ),
            sources,
        )

    def _compute(
        self,
        line: Line,
        start: Position,
        end: Position,
        window: GridWindow,
        downloaded: _Downloaded,
        sources: dict[str, Any],
        piezometers: list[PiezometerPoint],
        levels: dict[str, LevelsSource] | None,
    ) -> CrossSection:
        settings = self._settings
        section = settings.section
        ground_grid = warped(
            window,
            downloaded.terrain,
            float(settings.national.datasets.terrain.sea_value),
            Resampling.bilinear,
        )
        steps = max(1, math.ceil(line.length / section.sample_m))
        distances = [line.length * k / steps for k in range(steps + 1)]
        points = [line.point_at(d) for d in distances]
        grounds = [_sample(ground_grid, window, x, y) for x, y in points]

        labels = self._labels(window, downloaded.lithology, points)
        units, positions = surface_units(distances, labels, line.length)
        if all(label is None for label in labels):
            units, positions = [], []
        faults = self._faults(line, downloaded.faults)
        bedding = place_bedding(line, self._bedding(downloaded.bedding))
        boreholes = select_boreholes(line, self._boreholes(downloaded.water_points), section)
        boreholes = [
            b
            if b.ground_m is not None
            else b.model_copy(
                update={
                    "ground_m": _sample(
                        ground_grid,
                        window,
                        *line.point_at(min(max(b.distance_m, 0.0), line.length)),
                    )
                }
            )
            for b in boreholes
        ]
        contacts = contacts_of(line, positions, distances, grounds, bedding, faults, section)
        columns = columns_of(
            line,
            distances,
            grounds,
            units,
            contacts,
            faults,
            bedding,
            boreholes,
            section,
            settings.model.confidence,
        )
        table, used = self._water_table(
            line, window, downloaded.bodies, ground_grid, piezometers, levels
        )

        gaps = [SectionGap.NO_BOREHOLE_LOGS]
        if not units:
            gaps.append(SectionGap.NO_UNITS)
        if not bedding:
            gaps.append(SectionGap.NO_BEDDING)
        if not boreholes:
            gaps.append(SectionGap.NO_BOREHOLES)
        if all(p.state == "unknown" for p in table):
            gaps.append(SectionGap.NO_WATER_TABLE)
        if any(g is None for g in grounds):
            gaps.append(SectionGap.GROUND_INCOMPLETE)
        return CrossSection(
            start=start,
            end=end,
            crs=window.crs,
            length_m=line.length,
            azimuth_deg=line.azimuth_deg,
            built_at=self._clock(),
            column_m=line.length / len(columns),
            row_m=section.row_m,
            depth_m=section.depth_m,
            profile=tuple(
                ProfilePoint(distance_m=d, ground_m=g)
                for d, g in zip(distances, grounds, strict=True)
            ),
            units=tuple(units),
            contacts=tuple(contacts),
            faults=tuple(faults),
            bedding=tuple(bedding),
            boreholes=tuple(boreholes),
            water_table=tuple(table),
            columns=tuple(columns),
            sources=sources,
            levels=tuple(s for key, s in (levels or {}).items() if key in used),
            gaps=tuple(gaps),
        )

    def _labels(
        self, window: GridWindow, features: Features, points: list[tuple[float, float]]
    ) -> list[str | None]:
        """The mapped unit's description at each sample (None where there is none)."""
        field = self._settings.section.lithology.label_field
        names: list[str] = []
        codes: dict[str, int] = {}
        shapes = []
        for feature in features:
            geometry = feature.get("geometry")
            name = _text((feature.get("properties") or {}).get(field))
            if not name or not isinstance(geometry, dict):
                continue
            if name not in codes:
                codes[name] = len(names)
                names.append(name)
            shapes.append((geometry, float(codes[name])))
        grid = burn(window, shapes, fill=float(_ABSENT))
        labels: list[str | None] = []
        for x, y in points:
            code = _sample(grid, window, x, y)
            labels.append(None if code is None or code < 0 else names[int(code)])
        return labels

    def _faults(self, line: Line, features: Features) -> list[FaultCrossing]:
        faults = self._settings.parcel.faults
        found: list[FaultCrossing] = []
        for feature in features:
            kind = _text((feature.get("properties") or {}).get(faults.type_field))
            if not faults.is_fault(kind):
                continue
            for vertices in line_vertices(feature.get("geometry")):
                found.extend(
                    FaultCrossing(distance_m=d, kind=kind) for d in line.crossings(vertices)
                )
        return sorted(found, key=lambda f: f.distance_m)

    def _bedding(self, features: Features) -> list[BeddingPoint]:
        """The bedding measurements (the middle of each symbol's line), with their dip and
        dip direction; one without a dip is left out."""
        bedding = self._settings.parcel.bedding
        direction_field = self._settings.section.bedding_direction_field
        kinds = set(bedding.kinds)
        found = []
        for feature in features:
            properties = feature.get("properties") or {}
            kind = _text(properties.get(bedding.kind_field))
            dip = _number(properties.get(bedding.dip_field))
            if kind not in kinds or dip is None or not 0 <= dip <= 90:
                continue
            direction = _number(properties.get(direction_field))
            if direction is not None and not 0 <= direction <= 360:
                direction = None
            for vertices in line_vertices(feature.get("geometry"))[:1]:
                if vertices:
                    (x0, y0), (x1, y1) = vertices[0], vertices[-1]
                    found.append(BeddingPoint((x0 + x1) / 2, (y0 + y1) / 2, dip, direction, kind))
        return found

    def _boreholes(self, features: Features) -> list[BoreholePoint]:
        dataset = self._settings.national.datasets.water_points
        boreholes = self._settings.section.boreholes
        found = []
        for feature in features:
            properties = feature.get("properties") or {}
            kind = _text(properties.get(dataset.kind_field))
            depth = _number(properties.get(boreholes.depth_field))
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if (
                kind in dataset.exclude_kinds
                or not kind
                or depth is None
                or depth <= 0
                or geometry.get("type") != "Point"
                or not isinstance(coordinates, list)
                or len(coordinates) < 2
            ):
                continue
            ground = _number(properties.get(boreholes.ground_field))
            found.append(
                BoreholePoint(
                    x=float(coordinates[0]),
                    y=float(coordinates[1]),
                    kind=kind,
                    depth_m=depth,
                    # 0 is the inventory's blank, not sea level.
                    ground_m=ground if ground else None,
                )
            )
        return found

    def _water_table(
        self,
        line: Line,
        window: GridWindow,
        bodies: Features,
        ground: FloatGrid,
        piezometers: list[PiezometerPoint],
        levels: dict[str, LevelsSource] | None,
    ) -> tuple[list[WaterTablePoint], set[str]]:
        """Session 07's water table every ``water_table_every_m`` along the line, and the
        services of the levels used."""
        settings = self._settings
        dataset = settings.national.datasets.groundwater_bodies
        codes, categories = body_grid(window, bodies, dataset, settings.model)
        every = settings.section.water_table_every_m
        steps = max(1, math.ceil(line.length / every))
        points: list[WaterTablePoint] = []
        used: set[str] = set()
        for k in range(steps + 1):
            distance = line.length * k / steps
            x, y = line.point_at(distance)
            code = _sample(codes, window, x, y)
            body = None if code is None or code < 0 else categories[int(code)]
            elevation = _sample(ground, window, x, y)
            depth = depth_at(
                x,
                y,
                math.nan if elevation is None else elevation,
                None if body is None else (body.cls, body.label),
                piezometers,
                settings.piezometry.water_table,
                False,
                levels,
            )
            if depth.water_table is None:
                points.append(
                    WaterTablePoint(distance_m=distance, state="unknown", reason=depth.reason)
                )
                continue
            used.update(s.service_id for s in depth.sources)
            points.append(
                WaterTablePoint(
                    distance_m=distance, state="estimated", water_table=depth.water_table
                )
            )
        return points, used


__all__ = ["SectionService"]
