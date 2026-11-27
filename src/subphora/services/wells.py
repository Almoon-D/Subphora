# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The owner's well registry and what the map learns from it (MASTER_PLAN §4.3 Learning,
§3 Privacy; decision 0040).

- The registry is the private store in ``data/``; this service checks each record
  against the settings before the store keeps it, and reads CSV imports.
- The detailed map's layer "updated with your wells" is computed when asked, from the
  area's stored index and the wells known now, so a well logged a moment ago shows at
  once and the area's own map is never changed: the two layers can be compared.
- A tap on the detailed map gets the same update at that point, with every well that
  moved it, and the depth to water there twice: from the public piezometry alone, and with
  the owner's wells read at rest as private levels of their own groundwater body (never
  a reading taken while pumping). Both are computed when asked; the area's stored map,
  its candidates, its report and its export pack keep the public depth.
- Readings come one by one from the panel, or in batches from the device's outbox, each
  kept once under its id.
- The owner's wells validate the national index apart from the public wells, per domain,
  productive against dry, with decision 0030's method and thresholds.
- Nothing here logs a record's content (a name, a position, a note).
"""

import asyncio
import hashlib
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from subphora.config import Settings
from subphora.domain.depth import OwnLevel
from subphora.domain.parcel_map import ParcelError, ParcelExplanation, ParcelFailure
from subphora.domain.potential import Variable
from subphora.domain.validation import NO_BODY, DomainValidation
from subphora.domain.wells import (
    KNOWN_OUTCOMES,
    Change,
    DepthWithWells,
    ImportReport,
    LevelLeftOut,
    OwnerValidation,
    PumpState,
    ReadingResult,
    Registry,
    Well,
    WellOutcome,
    WellReading,
    WellRecord,
    WellSaved,
    WellsError,
    WellsFailure,
)
from subphora.geo.grid import GridWindow, transform_xy
from subphora.geo.render import overlay_image, transparent_png
from subphora.model.depth import PiezometerPoint, depth_at
from subphora.model.evaluate import Category
from subphora.model.learning import KnownWell, update_at, update_grid
from subphora.model.validation import Labelled, probabilities, validate_domain
from subphora.services.national_map import estimate_at
from subphora.services.parcel import ParcelMapService
from subphora.services.piezometry import piezometer_points, summarise
from subphora.services.validation import domain_codes
from subphora.services.wells_csv import parse_wells_csv
from subphora.store.file_cache import Clock, utc_now
from subphora.store.national import (
    RegionManifest,
    read_bands,
    read_manifest,
    read_manifests,
    region_tif,
)
from subphora.store.piezometry import read_piezometry
from subphora.store.wells import WellsStore

_LON_LAT = "EPSG:4326"
_STAMP_LENGTH = 16
# The seed's salt of the owner's validation, apart from every build region's.
_VALIDATION_SALT = 0x0E11


class WellsService:
    def __init__(self, settings: Settings, root: Path, clock: Clock = utc_now) -> None:
        self._settings = settings
        self._wells = settings.wells
        store = self._wells.store
        self._store = WellsStore(store.database_path(root), store.busy_timeout_s)
        self._national_root = settings.national.build.output_path(root)
        self._levels_path = settings.piezometry.output_path(root)
        self._clock = clock

    # ── The registry ───────────────────────────────────────────────────────────────────

    async def registry(self) -> Registry:
        records = await self._store.records()
        return Registry(wells=tuple(records), stamp=self.stamp(records))

    def stamp(self, records: Sequence[WellRecord]) -> str:
        """Changes whenever a well that updates the map, or the update's settings, change."""
        known = sorted(
            (r.well.id, r.well.longitude, r.well.latitude, r.well.outcome.value)
            for r in records
            if r.well.outcome in KNOWN_OUTCOMES
        )
        text = repr((known, self._wells.update.model_dump_json()))
        return hashlib.sha256(text.encode()).hexdigest()[:_STAMP_LENGTH]

    async def current_stamp(self) -> str:
        """The registry's stamp; a failing registry gets a stamp of its own, so that the
        detailed map still answers (its layer of the wells then says the registry failed)."""
        try:
            return self.stamp(await self._store.records())
        except WellsError:
            return hashlib.sha256(b"unavailable").hexdigest()[:_STAMP_LENGTH]

    def _check(self, well: Well) -> None:
        if len(well.name) > self._wells.name_max_chars:
            raise WellsError(
                WellsFailure.INVALID_WELL,
                f"a name has at most {self._wells.name_max_chars} characters",
            )
        if well.note is not None and len(well.note) > self._wells.note_max_chars:
            raise WellsError(
                WellsFailure.INVALID_WELL,
                f"a note has at most {self._wells.note_max_chars} characters",
            )

    async def save(self, well: Well) -> WellSaved:
        self._check(well)
        return WellSaved(id=well.id, change=await self._store.put(well))

    async def delete(self, well_id: str) -> None:
        if not await self._store.delete(well_id):
            raise WellsError(WellsFailure.UNKNOWN_WELL, f"no well {well_id}")

    async def add_reading(self, reading: WellReading) -> WellSaved:
        change = await self._store.add_reading(reading)
        if change is Change.CONFLICT:
            raise WellsError(
                WellsFailure.CONFLICT, f"the reading {reading.id} is held with other content"
            )
        return WellSaved(id=reading.id, change=change)

    async def add_readings(self, readings: Sequence[WellReading]) -> list[ReadingResult]:
        """A batch from the device's outbox: each reading kept once, or refused on its own."""
        limit = self._settings.field.sync.batch_size
        if len(readings) > limit:
            raise WellsError(WellsFailure.TOO_LARGE, f"at most {limit} readings a request")
        return await self._store.add_readings(readings)

    async def import_csv(self, content: bytes) -> ImportReport:
        parsed = await asyncio.to_thread(parse_wells_csv, content, self._wells)
        return await self._store.import_rows(parsed.rows, parsed.wells, parsed.readings)

    async def records_within(
        self, bbox: tuple[float, float, float, float]
    ) -> tuple[WellRecord, ...]:
        """The wells inside a box in degrees (west, south, east, north)."""
        west, south, east, north = bbox
        return tuple(
            r
            for r in await self._store.records()
            if west <= r.well.longitude <= east and south <= r.well.latitude <= north
        )

    async def _known(self, crs: str) -> list[KnownWell]:
        """The wells whose outcome is known, in ``crs``."""
        known = []
        for record in await self._store.records():
            well = record.well
            if well.outcome is WellOutcome.PRODUCTIVE or well.outcome is WellOutcome.DRY:
                x, y = transform_xy(well.longitude, well.latitude, _LON_LAT, crs)
                known.append(KnownWell(id=well.id, outcome=well.outcome, x=x, y=y))
        return known

    # ── The detailed map updated with the wells ────────────────────────────────────────

    async def layer(self, maps: ParcelMapService, area_id: str) -> bytes:
        """The area's layer updated with the wells known now, as one PNG (a transparent
        pixel where no cell has a value)."""
        analysis = await maps.analysis(area_id)
        wells = await self._known(analysis.crs)
        png = await asyncio.to_thread(self._layer, maps.root, area_id, wells)
        return png or transparent_png(1)

    @staticmethod
    def _manifest(root: Path, area_id: str) -> RegionManifest:
        try:
            manifest = read_manifest(root, area_id)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc
        if manifest is None:
            raise ParcelError(ParcelFailure.UNREADABLE, f"the grid of {area_id} is missing")
        return manifest

    def _layer(self, root: Path, area_id: str, wells: Sequence[KnownWell]) -> bytes | None:
        manifest = self._manifest(root, area_id)
        names = [Variable.INDEX.value, Variable.GROUNDWATER_BODY.value]
        try:
            bands, transform, crs = read_bands(region_tif(root, area_id), names)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc
        prior = prior_grid(bands[Variable.INDEX.value], bands[names[1]], manifest)
        updated = update_grid(
            prior, manifest.west, manifest.north, manifest.cell_m, wells, self._wells.update
        )
        legend = self._settings.national.tiles.layer(self._wells.update.legend_layer)
        png, _ = overlay_image(
            updated,
            transform,
            crs,
            legend.breaks,
            legend.colours,
            self._settings.parcel.image_max_px,
        )
        return png

    async def explain(
        self, maps: ParcelMapService, area_id: str, lon: float, lat: float
    ) -> ParcelExplanation:
        """The detailed map's estimate at a point, with its value updated by the wells and
        the depth to water with the owner's levels beside the public one."""
        explanation = await maps.explain(area_id, lon, lat)
        records = await self._store.records()
        depth = await asyncio.to_thread(
            self._depth, maps.root, area_id, lon, lat, records, self._clock()
        )
        estimate = explanation.estimate
        updated = None
        if estimate.score is not None:
            analysis = await maps.analysis(area_id)
            wells = await self._known(analysis.crs)
            kind: Literal["index", "probability"]
            if estimate.probability is not None:
                prior, kind = estimate.probability.value, "probability"
            else:
                prior, kind = estimate.score, "index"
            x, y = transform_xy(lon, lat, _LON_LAT, analysis.crs)
            updated = update_at(prior, kind, x, y, wells, self._wells.update)
        return ParcelExplanation(
            longitude=explanation.longitude,
            latitude=explanation.latitude,
            area_id=explanation.area_id,
            cell_m=explanation.cell_m,
            built_at=explanation.built_at,
            estimate=estimate,
            updated=updated,
            depth=depth,
        )

    # ── The depth to water with the owner's levels ─────────────────────────────────────

    def _depth(
        self,
        root: Path,
        area_id: str,
        lon: float,
        lat: float,
        records: Sequence[WellRecord],
        now: datetime,
    ) -> DepthWithWells:
        """The depth at a point of an area, public and with the owner's levels. Blocks."""
        grid = _AreaGrid.read(root, self._manifest(root, area_id))
        x, y = transform_xy(lon, lat, _LON_LAT, grid.window.crs)
        cell = grid.window.cell_of(x, y)
        if cell is None:
            raise ParcelError(ParcelFailure.OUTSIDE_GRID, "the point lies outside the area")
        try:
            levels = read_piezometry(self._levels_path)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc
        piezometry = self._settings.piezometry
        table = piezometry.water_table
        public = (
            []
            if levels is None
            else piezometer_points(levels, grid.window.crs, (x, y, x, y), table.max_distance_m)
        )
        own, points, left_out = self._own_levels(grid, records, now)
        ground = grid.ground(cell)
        body = grid.body(cell)
        permeability = grid.permeability(cell)
        karst = permeability is not None and piezometry.is_karst(permeability)
        sources = None if levels is None else levels.source_map()
        site = (x, y, ground, body)
        return DepthWithWells(
            public=depth_at(*site, public, table, karst, sources),
            with_wells=depth_at(*site, [*public, *points], table, karst, sources, own),
            left_out=left_out,
        )

    def _unusable(self, reading: WellReading) -> LevelLeftOut | None:
        """Why a reading is no level of the water table, or None: it was read at rest."""
        if reading.pump is PumpState.RUNNING:
            return LevelLeftOut.PUMPING
        if reading.pump is PumpState.UNKNOWN:
            return LevelLeftOut.PUMP_UNKNOWN
        rest = self._wells.levels.min_rest_minutes
        if reading.pump_minutes is not None and reading.pump_minutes < rest:
            return LevelLeftOut.RECOVERING
        return None

    def _own_levels(
        self, grid: _AreaGrid, records: Sequence[WellRecord], now: datetime
    ) -> tuple[dict[str, OwnLevel], list[PiezometerPoint], dict[LevelLeftOut, int]]:
        """The owner's wells inside the area's grid as private levels of their own body,
        from their readings at rest; and the readings left out, by why."""
        own: dict[str, OwnLevel] = {}
        points: list[PiezometerPoint] = []
        left_out: Counter[LevelLeftOut] = Counter()
        summary = self._wells.levels.summary
        for record in records:
            at_rest = []
            for reading in record.readings:
                reason = self._unusable(reading)
                if reason is None:
                    at_rest.append(reading)
                else:
                    left_out[reason] += 1
            if not at_rest:
                continue
            well = record.well
            x, y = transform_xy(well.longitude, well.latitude, _LON_LAT, grid.window.crs)
            depths = [(r.measured_at.astimezone(UTC).date(), r.below_ground_m) for r in at_rest]
            placed = _placed(grid, grid.window.cell_of(x, y))
            summarised = summarise(depths, summary, now.date())
            if isinstance(placed, LevelLeftOut) or summarised is None:
                left_out[placed if isinstance(placed, LevelLeftOut) else LevelLeftOut.TOO_OLD] += (
                    len(at_rest)
                )
                continue
            ground, body = placed
            # The depths' range turns over into the levels': the deepest water is the lowest.
            level = OwnLevel(
                well_id=well.id,
                distance_m=0.0,
                ground_m=ground,
                level_m=ground - summarised.level,
                low_m=ground - summarised.high,
                high_m=ground - summarised.low,
                readings=summarised.count,
                first=summarised.first,
                last=summarised.last,
            )
            own[well.id] = level
            points.append(
                PiezometerPoint(
                    x=x,
                    y=y,
                    body=body[0],
                    level_m=level.level_m,
                    low_m=level.low_m,
                    high_m=level.high_m,
                    well_id=well.id,
                )
            )
        return own, points, dict(left_out)

    # ── The index against the owner's wells ────────────────────────────────────────────

    async def validation(self) -> OwnerValidation:
        records = await self._store.records()
        return await asyncio.to_thread(self._validate, records, self._clock())

    def _validate(self, records: Sequence[WellRecord], now: datetime) -> OwnerValidation:
        try:
            manifests = read_manifests(self._national_root)
        except ValueError:
            manifests = []
        labels: dict[
            str, tuple[str, list[tuple[float, float, float]], list[tuple[float, float, float]]]
        ] = {}
        off_map = unknown = 0
        for record in records:
            well = record.well
            if well.outcome not in KNOWN_OUTCOMES:
                unknown += 1
                continue
            scored = _score(self._national_root, manifests, well)
            if scored is None:
                off_map += 1
                continue
            validation, score, x, y = scored
            _, productive, dry = labels.setdefault(validation.domain, (validation.label, [], []))
            (productive if well.outcome is WellOutcome.PRODUCTIVE else dry).append((score, x, y))
        settings = self._settings.validation
        rng = np.random.default_rng([settings.seed, _VALIDATION_SALT])
        source = self._wells.validation.labels_source
        empty = Labelled.of([], [], settings.block_m)
        validations = []
        for domain in sorted(labels, key=lambda d: (d == NO_BODY, d)):
            label, productive, dry = labels[domain]
            validations.append(
                validate_domain(
                    domain,
                    label,
                    _labelled(productive, settings.block_m),
                    _labelled(dry, settings.block_m),
                    empty,
                    settings,
                    now,
                    rng,
                    dry_labels=True,
                    labels_source=source,
                    excluded_criteria=(),
                )
            )
        return OwnerValidation(
            validations=tuple(validations), off_map=off_map, unknown_outcome=unknown
        )


@dataclass(frozen=True, slots=True)
class _AreaGrid:
    """What the depth needs of an area's stored grid: its window, the ground elevation,
    the groundwater body and the permeability class at each cell, and their categories."""

    window: GridWindow
    elevation: NDArray[np.float32]
    bodies: NDArray[np.float32]
    permeabilities: NDArray[np.float32]
    body_categories: tuple[Category, ...]
    permeability_categories: tuple[Category, ...]

    @classmethod
    def read(cls, root: Path, manifest: RegionManifest) -> _AreaGrid:
        names = [
            Variable.ELEVATION_M.value,
            Variable.GROUNDWATER_BODY.value,
            Variable.PERMEABILITY_CLASS.value,
        ]
        try:
            bands, _, _ = read_bands(region_tif(root, manifest.region_id), names)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc

        def categories(variable: Variable) -> tuple[Category, ...]:
            items = manifest.categories.get(variable, ())
            return tuple(Category(cls=c.cls, label=c.label) for c in items)

        return cls(
            window=GridWindow(
                crs=manifest.crs,
                cell_m=manifest.cell_m,
                west=manifest.west,
                north=manifest.north,
                width=manifest.width,
                height=manifest.height,
            ),
            elevation=bands[names[0]],
            bodies=bands[names[1]],
            permeabilities=bands[names[2]],
            body_categories=categories(Variable.GROUNDWATER_BODY),
            permeability_categories=categories(Variable.PERMEABILITY_CLASS),
        )

    def ground(self, cell: tuple[int, int]) -> float:
        return float(self.elevation[cell])

    @staticmethod
    def _category(
        grid: NDArray[np.float32], items: Sequence[Category], cell: tuple[int, int]
    ) -> Category | None:
        value = float(grid[cell])
        code = -1 if math.isnan(value) else int(value)
        return items[code] if 0 <= code < len(items) else None

    def body(self, cell: tuple[int, int]) -> tuple[str, str] | None:
        """The (code, label) of the groundwater body at a cell; None outside every body."""
        found = self._category(self.bodies, self.body_categories, cell)
        return None if found is None else (found.cls, found.label)

    def permeability(self, cell: tuple[int, int]) -> str | None:
        found = self._category(self.permeabilities, self.permeability_categories, cell)
        return None if found is None else found.label


def _placed(
    grid: _AreaGrid, cell: tuple[int, int] | None
) -> tuple[float, tuple[str, str]] | LevelLeftOut:
    """A well's ground elevation and groundwater body from the area's grid, or why not."""
    if cell is None:
        return LevelLeftOut.OUTSIDE_AREA
    ground = grid.ground(cell)
    if math.isnan(ground):
        return LevelLeftOut.NO_GROUND_ELEVATION
    body = grid.body(cell)
    if body is None:
        return LevelLeftOut.OUTSIDE_BODIES
    return ground, body


def _labelled(points: Sequence[tuple[float, float, float]], block_m: float) -> Labelled:
    return Labelled.of([s for s, _, _ in points], [(x, y) for _, x, y in points], block_m)


def _score(
    root: Path, manifests: Sequence[RegionManifest], well: Well
) -> tuple[DomainValidation, float, float, float] | None:
    """A well's domain, its national index and its position in that region's CRS; None
    where no region of the national map scores it."""
    lon, lat = well.longitude, well.latitude
    for manifest in manifests:
        west, south, east, north = manifest.bbox
        if not (west <= lon <= east and south <= lat <= north):
            continue
        estimate = estimate_at(root, manifest, lon, lat)
        if estimate is None or estimate.score is None:
            continue
        x, y = transform_xy(lon, lat, _LON_LAT, manifest.crs)
        return estimate.validation, estimate.score, x, y
    return None


def prior_grid(
    index: NDArray[np.floating], body: NDArray[np.floating], manifest: RegionManifest
) -> NDArray[np.float64]:
    """The value the wells update at each cell: the calibrated probability where the
    cell's domain is calibrated, the index elsewhere."""
    prior = np.asarray(index, dtype=np.float64).copy()
    categories = [
        Category(cls=c.cls, label=c.label)
        for c in manifest.categories.get(Variable.GROUNDWATER_BODY, ())
    ]
    codes = domain_codes(body, categories)
    keys = [c.cls for c in categories] + [NO_BODY]
    for code, domain in enumerate(keys):
        calibration = manifest.validation_of(domain).calibration
        if calibration is None:
            continue
        inside = codes == code
        prior[inside] = probabilities(calibration, prior[inside])
    return prior


__all__ = ["WellsService", "prior_grid"]
