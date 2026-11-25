# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The published national map: its description, its tiles and the explanation of a cell.

Everything is read from what the last build wrote (``data/national``). A region is
explained with the model settings and input sources of its own build, so a tap always
agrees with the tiles drawn from that build.
"""

import asyncio
import math
from pathlib import Path

from subphora.config import Settings
from subphora.domain.potential import (
    CATEGORICAL,
    RESULTS,
    CellExplanation,
    NationalError,
    NationalFailure,
    PotentialEstimate,
    Variable,
)
from subphora.geo import tile_exists
from subphora.geo.grid import GridWindow, transform_xy
from subphora.geo.render import transparent_png
from subphora.model import Category, Quality, explain_cell
from subphora.store.national import (
    MapManifest,
    RegionManifest,
    TileArchive,
    map_path,
    read_cell,
    read_manifests,
    read_map,
    tiles_path,
)

_LON_LAT = "EPSG:4326"


def _holds(bbox: tuple[float, float, float, float], lon: float, lat: float) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


class NationalMapService:
    def __init__(self, settings: Settings, root: Path) -> None:
        self._settings = settings.national
        self._root = settings.national.build.output_path(root)
        self._archives: dict[str, TileArchive] = {}
        self._empty = transparent_png(settings.national.tiles.tile_size)
        # The regions read for the map.json of this modification time.
        self._regions: tuple[int, list[RegionManifest]] | None = None
        self._lock = asyncio.Lock()

    def close(self) -> None:
        """Close the tile archives the server has open."""
        for archive in self._archives.values():
            archive.close()

    async def describe(self) -> MapManifest | None:
        try:
            return await asyncio.to_thread(read_map, self._root)
        except ValueError as exc:
            raise NationalError(NationalFailure.UNREADABLE, f"map.json: {exc}") from exc

    async def tile(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        try:
            self._settings.tiles.layer(layer_id)
        except KeyError:
            raise NationalError(NationalFailure.UNKNOWN_LAYER, f"no layer {layer_id!r}") from None
        if not tile_exists(z, x, y):
            raise NationalError(NationalFailure.INVALID_TILE, f"no tile {z}/{x}/{y}")
        archive = self._archives.setdefault(layer_id, TileArchive(tiles_path(self._root, layer_id)))
        content = await asyncio.to_thread(archive.get, z, x, y)
        if content is not None:
            return content
        if not tiles_path(self._root, layer_id).exists():
            raise NationalError(NationalFailure.NOT_BUILT, "the national map is not built yet")
        # Inside the archive's bounds but without a value there (the sea, unbuilt regions).
        return self._empty

    async def _manifests(self) -> list[RegionManifest]:
        async with self._lock:
            try:
                stamp = map_path(self._root).stat().st_mtime_ns
            except FileNotFoundError:
                raise NationalError(
                    NationalFailure.NOT_BUILT, "the national map is not built yet"
                ) from None
            if self._regions is None or self._regions[0] != stamp:
                try:
                    regions = await asyncio.to_thread(read_manifests, self._root)
                except ValueError as exc:
                    raise NationalError(NationalFailure.UNREADABLE, str(exc)) from exc
                self._regions = (stamp, regions)
            return self._regions[1]

    async def explain(self, lon: float, lat: float) -> CellExplanation:
        for manifest in await self._manifests():
            if not _holds(manifest.bbox, lon, lat):
                continue
            estimate = await asyncio.to_thread(estimate_at, self._root, manifest, lon, lat)
            if estimate is None:
                continue  # outside the region's boundary
            return CellExplanation(
                longitude=lon,
                latitude=lat,
                grid=manifest.grid,
                region_id=manifest.region_id,
                region_name=manifest.name,
                cell_m=manifest.cell_m,
                built_at=manifest.built_at,
                estimate=estimate,
            )
        raise NationalError(
            NationalFailure.OUTSIDE_BUILT_AREA, "no region of the national map holds that point"
        )


def estimate_at(
    root: Path, manifest: RegionManifest, lon: float, lat: float
) -> PotentialEstimate | None:
    """The estimate of the stored grid's cell under a point, explained with the settings
    and sources of its own build; None outside the grid or where it has no input. Blocks."""
    window = GridWindow(
        crs=manifest.crs,
        cell_m=manifest.cell_m,
        west=manifest.west,
        north=manifest.north,
        width=manifest.width,
        height=manifest.height,
    )
    cell = window.cell_of(*transform_xy(lon, lat, _LON_LAT, manifest.crs))
    if cell is None:
        return None
    values = read_cell(root, manifest, *cell)
    inputs = {v: value for v, value in values.items() if v not in RESULTS}
    if all(math.isnan(value) for value in inputs.values()):
        return None
    return explain_cell(
        manifest.model,
        inputs,
        {
            v: [Category(cls=c.cls, label=c.label) for c in items]
            for v, items in manifest.categories.items()
            if v in CATEGORICAL
        },
        {k: Quality(resolution=q.resolution, age=q.age) for k, q in manifest.quality.items()},
        manifest.sources,
        values[Variable.WATER_POINT_DISTANCE_M],
        manifest.caps(),
    )
