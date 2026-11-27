# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What the report and the export pack are made from (MASTER_PLAN §4.6): a finished
detailed map, its outline and grids, the field records made there, and the catalogue
entries of every service it cites; and the pack's GIS files written from them.

- The maps are the detailed map's own grids, in its CRS (north up, metres), coloured by
  the national legend: no base map is fetched, so making a report calls no service.
- Field records belong to an area when they were made inside its box or guided to one of
  its spots. Their photos and voice memos join the pack only when the owner asks.
- The owner's wells inside the area's box join the pack only when the owner asks
  (decision 0040); otherwise the pack says they were left out, and the report never
  shows them.
- A layer that has nothing to hold (no depth without imported levels) is not written, and
  the pack lists it as missing with the reason.
"""

import asyncio
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import numpy as np
from affine import Affine
from numpy.typing import NDArray

from subphora.config import Settings
from subphora.config.national import TileLayer
from subphora.config.sources import Service
from subphora.domain.field import Observation
from subphora.domain.parcel_map import AreaAnalysis, Candidate, ParcelError, ParcelFailure
from subphora.domain.wells import WellRecord
from subphora.geo.export import FieldValue, VectorLayer, write_cog, write_gpkg
from subphora.geo.grid import Bounds, transform_xy
from subphora.geo.raster import Geometry
from subphora.geo.render import colour_png
from subphora.services.field import FieldService
from subphora.services.parcel import ParcelMapService
from subphora.services.wells import WellsService
from subphora.store.file_cache import Clock, utc_now
from subphora.store.national import read_bands, region_tif
from subphora.store.parcels import depth_path, read_outline

_LON_LAT = "EPSG:4326"
_DEPTH_BANDS = ("depth_m", "low_m", "high_m")


class Missing(StrEnum):
    """A part of the pack that is not there, and why."""

    # No piezometric levels were imported: no depth grid exists.
    DEPTH_NOT_IMPORTED = "depth_not_imported"
    # No field record was made in the area.
    NO_OBSERVATIONS = "no_observations"
    # Records have photos or voice memos, left out because the owner did not ask for them.
    MEDIA_LEFT_OUT = "media_left_out"
    # A record declares a file the server never received.
    MEDIA_NOT_RECEIVED = "media_not_received"
    # The owner has wells in the area, left out because the owner did not ask for them.
    WELLS_LEFT_OUT = "wells_left_out"


@dataclass(frozen=True, slots=True)
class MapFigure:
    """A layer of the detailed map as one image, north up, over ``bounds`` (west, south,
    east, north in the grid's CRS); ``png`` is None when no cell has a value."""

    layer: TileLayer
    png: bytes | None
    width_px: int
    height_px: int
    bounds: Bounds


@dataclass(frozen=True, slots=True)
class FieldRecord:
    observation: Observation
    # The stored photo or voice memo, if the server has it.
    file: Path | None
    # The position in the grid's CRS; None without a position.
    local: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class ReportData:
    analysis: AreaAnalysis
    outline: tuple[Geometry, ...]
    maps: tuple[MapFigure, ...]
    # The catalogue entry of every service the analysis read, by id.
    services: dict[str, Service]
    records: tuple[FieldRecord, ...]
    depth_grid: bool
    generated_at: datetime
    # The owner's wells in the area's box, only when asked for; and whether any was left
    # out because they were not.
    wells: tuple[WellRecord, ...] = ()
    wells_left_out: bool = False


@dataclass(frozen=True, slots=True)
class PackFiles:
    """The GIS files written for the pack: (name in the pack, file), and what is missing."""

    files: tuple[tuple[str, Path], ...]
    missing: tuple[Missing, ...]


def _cited(analysis: AreaAnalysis) -> list[str]:
    ids = [source.service_id for source in analysis.sources.values()]
    for candidate in analysis.candidates:
        ids.extend(source.service_id for source in candidate.depth.sources)
    return list(dict.fromkeys(ids))


class ExportService:
    def __init__(
        self,
        settings: Settings,
        parcel: ParcelMapService,
        field: FieldService,
        wells: WellsService,
        clock: Clock = utc_now,
    ) -> None:
        self._settings = settings
        self._report = settings.report
        self._parcel = parcel
        self._field = field
        self._wells = wells
        self._clock = clock

    async def data(self, area_id: str, wells: bool = False) -> ReportData:
        """Everything the report shows (and the owner's wells there when ``wells``);
        raises ParcelError while the map is not done or when its files cannot be read."""
        analysis = await self._parcel.analysis(area_id)
        root = self._parcel.root
        try:
            outline = await asyncio.to_thread(read_outline, root, area_id)
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc
        if outline is None:
            raise ParcelError(ParcelFailure.UNREADABLE, f"the outline of {area_id} is missing")
        maps = await asyncio.to_thread(self._maps, area_id)
        services: dict[str, Service] = {}
        for service_id in _cited(analysis):
            try:
                services[service_id] = self._settings.sources.service(service_id)
            except KeyError:
                continue  # the report shows the source's own attribution without it
        records = tuple(
            FieldRecord(
                observation=observation,
                file=file,
                local=None
                if observation.position is None
                else transform_xy(
                    observation.position.longitude,
                    observation.position.latitude,
                    _LON_LAT,
                    analysis.crs,
                ),
            )
            for observation, file in await self._field.records_near(area_id, analysis.bbox)
        )
        held = await self._wells.records_within(analysis.bbox)
        return ReportData(
            analysis=analysis,
            outline=tuple(outline),
            maps=maps,
            services=services,
            records=records,
            depth_grid=depth_path(root, area_id).exists(),
            generated_at=self._clock(),
            wells=held if wells else (),
            wells_left_out=bool(held) and not wells,
        )

    def _layers(self) -> list[TileLayer]:
        tiles = self._settings.national.tiles
        return [tiles.layer(layer_id) for layer_id in self._report.layers]

    def _grids(self, area_id: str) -> tuple[dict[str, NDArray[np.float32]], Affine, str]:
        try:
            return read_bands(
                region_tif(self._parcel.root, area_id),
                [layer.variable.value for layer in self._layers()],
            )
        except ValueError as exc:
            raise ParcelError(ParcelFailure.UNREADABLE, str(exc)) from exc

    def _maps(self, area_id: str) -> tuple[MapFigure, ...]:
        bands, transform, _crs = self._grids(area_id)
        figures = []
        for layer in self._layers():
            grid = bands[layer.variable.value]
            height, width = grid.shape
            step = max(1, -(-max(height, width) // self._report.map_max_px))
            shown = grid[::step, ::step]
            west, north = transform.c, transform.f
            east = west + width * transform.a
            south = north + height * transform.e
            figures.append(
                MapFigure(
                    layer=layer,
                    png=colour_png(shown, layer.breaks, layer.colours),
                    width_px=shown.shape[1],
                    height_px=shown.shape[0],
                    bounds=(west, south, east, north),
                )
            )
        return tuple(figures)

    async def write_layers(self, data: ReportData, folder: Path, media: bool) -> PackFiles:
        """The pack's COGs, GeoPackage and (when asked) media files under ``folder``."""
        return await asyncio.to_thread(self._write_layers, data, folder, media)

    def _write_layers(self, data: ReportData, folder: Path, media: bool) -> PackFiles:
        analysis = data.analysis
        area_id = analysis.id
        pack = self._report.pack
        files: list[tuple[str, Path]] = []
        missing: list[Missing] = []
        bands, transform, crs = self._grids(area_id)
        for layer in self._layers():
            name = f"{layer.id}.tif"
            write_cog(
                folder / name,
                {layer.variable.value: bands[layer.variable.value]},
                transform,
                crs,
                pack.cog_blocksize,
                pack.cog_compress,
            )
            files.append((name, folder / name))
        if data.depth_grid:
            depth, depth_transform, depth_crs = read_bands(
                depth_path(self._parcel.root, area_id), _DEPTH_BANDS
            )
            write_cog(
                folder / "depth.tif",
                depth,
                depth_transform,
                depth_crs,
                pack.cog_blocksize,
                pack.cog_compress,
            )
            files.append(("depth.tif", folder / "depth.tif"))
        else:
            missing.append(Missing.DEPTH_NOT_IMPORTED)
        media_files: dict[str, str] = {}
        with_media = [r for r in data.records if r.observation.media is not None]
        if media:
            for record in with_media:
                if record.file is None or not record.file.exists():
                    if Missing.MEDIA_NOT_RECEIVED not in missing:
                        missing.append(Missing.MEDIA_NOT_RECEIVED)
                    continue
                name = f"media/{record.file.name}"
                (folder / "media").mkdir(exist_ok=True)
                shutil.copyfile(record.file, folder / name)
                files.append((name, folder / name))
                media_files[record.observation.id] = name
        elif with_media:
            missing.append(Missing.MEDIA_LEFT_OUT)
        if not data.records:
            missing.append(Missing.NO_OBSERVATIONS)
        if data.wells_left_out:
            missing.append(Missing.WELLS_LEFT_OUT)
        gpkg = folder / "layers.gpkg"
        write_gpkg(
            gpkg,
            [
                self._area_layer(data),
                _candidates_layer(analysis.candidates),
                _records_layer(data.records, media_files),
            ],
            analysis.crs,
        )
        files.append(("layers.gpkg", gpkg))
        return PackFiles(files=tuple(files), missing=tuple(missing))

    def _area_layer(self, data: ReportData) -> VectorLayer:
        analysis = data.analysis
        return VectorLayer(
            name="area",
            geometry_type="Polygon",
            fields=("area_id", "label", "area_m2", "built_at"),
            features=tuple(
                (
                    polygon["coordinates"],
                    {
                        "area_id": analysis.id,
                        "label": analysis.label,
                        "area_m2": analysis.area_m2,
                        "built_at": analysis.built_at.isoformat(),
                    },
                )
                for polygon in data.outline
            ),
        )


_CANDIDATE_FIELDS = (
    "rank",
    "longitude",
    "latitude",
    "kind",
    "index",
    "confidence",
    "confidence_label",
    "probability",
    "depth_state",
    "depth_unknown_reason",
    "depth_m",
    "depth_low_m",
    "depth_high_m",
    "karst",
    "cost_low_eur",
    "cost_high_eur",
    "legal_state",
    "authority",
    "water_point_m",
)


def _candidate_fields(candidate: Candidate) -> dict[str, FieldValue]:
    estimate, depth, cost = candidate.estimate, candidate.depth, candidate.cost
    authority = candidate.legal.authority
    return {
        "rank": candidate.rank,
        "longitude": candidate.longitude,
        "latitude": candidate.latitude,
        "kind": estimate.kind,
        "index": estimate.score,
        "confidence": estimate.confidence.value,
        "confidence_label": estimate.confidence.label.value,
        "probability": None if estimate.probability is None else estimate.probability.value,
        "depth_state": depth.state,
        "depth_unknown_reason": None if depth.reason is None else depth.reason.value,
        "depth_m": depth.depth_m,
        "depth_low_m": depth.low_m,
        "depth_high_m": depth.high_m,
        "karst": str(depth.karst).lower(),
        "cost_low_eur": None if cost is None else str(cost.low),
        "cost_high_eur": None if cost is None else str(cost.high),
        "legal_state": candidate.legal.state.value,
        "authority": None if authority is None else authority.name,
        "water_point_m": candidate.site.water_point.metres,
    }


def _candidates_layer(candidates: tuple[Candidate, ...]) -> VectorLayer:
    return VectorLayer(
        name="candidates",
        geometry_type="Point",
        fields=_CANDIDATE_FIELDS,
        features=tuple(((c.local.x, c.local.y), _candidate_fields(c)) for c in candidates),
    )


_RECORD_FIELDS = (
    "id",
    "kind",
    "recorded_at",
    "accuracy_m",
    "text",
    "target_area",
    "target_rank",
    "track_id",
    "media_type",
    "media_file",
)


def _records_layer(records: tuple[FieldRecord, ...], media_files: dict[str, str]) -> VectorLayer:
    """The records with a position (a record without one is in the CSV table only)."""
    features = []
    for record in records:
        if record.local is None:
            continue
        o = record.observation
        features.append(
            (
                record.local,
                {
                    "id": o.id,
                    "kind": o.kind.value,
                    "recorded_at": o.recorded_at.isoformat(),
                    "accuracy_m": None if o.position is None else o.position.accuracy_m,
                    "text": o.text,
                    "target_area": None if o.target is None else o.target.area_id,
                    "target_rank": None if o.target is None else o.target.rank,
                    "track_id": o.track_id,
                    "media_type": None if o.media is None else o.media.content_type,
                    "media_file": media_files.get(o.id),
                },
            )
        )
    return VectorLayer(
        name="observations", geometry_type="Point", fields=_RECORD_FIELDS, features=tuple(features)
    )


__all__ = [
    "ExportService",
    "FieldRecord",
    "MapFigure",
    "Missing",
    "PackFiles",
    "ReportData",
]
