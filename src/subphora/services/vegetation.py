# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Downloading the late-summer vegetation input of a build region (decision 0041).

- Scenes: a STAC search per summer over the region, then per Sentinel-2 tile the
  ``scenes_per_year`` least cloudy scenes under ``max_cloud_pct``.
- Composites: per Sentinel-2 tile, the red, NIR and scene-classification overviews of
  those scenes, read by GDAL in a thread (at most the pixel service's ``max_concurrent``
  at a time), become one NDVI composite (``geo.vegetation``), cached as a GeoTIFF under
  the scenes it was made of: a neighbouring region reuses it, and a past summer never
  changes.
- The irrigation mask: SIGPAC's vector tiles over the region, their irrigated enclosures
  burnt into a fine raster per tile and averaged onto the region's grid as the share of
  each cell that is irrigated. The service answers 404 for some large tiles whose four
  children it serves, so a 404 is asked again one zoom deeper, down to ``deepest_zoom``;
  a 404 there holds no enclosure (the sea). Each tile's burnt raster is cached, never the
  tile itself: a province's tiles weigh hundreds of megabytes.

Everything goes through the catalogue client and the file cache; nothing here computes
the anomaly itself, which the build's worker does from these inputs.
"""

import asyncio
import hashlib
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from affine import Affine
from rasterio.enums import Resampling as GdalResampling

from subphora.config.national import IrrigationMask, VegetationDataset
from subphora.geo.grid import GridWindow, buffered, lon_lat_bounds
from subphora.geo.raster import (
    FloatGrid,
    Resampling,
    burn_box,
    read_geotiff,
    warp_into,
    write_geotiff,
)
from subphora.geo.tiles import tile_bounds, tiles_covering
from subphora.geo.vector_tiles import VectorTileError, polygons_at_least
from subphora.geo.vegetation import composite, ndvi
from subphora.services.fetching import Fetched
from subphora.services.inputs import InputFailure, InputFetcher
from subphora.sources import CatalogueClient, HostNotAllowedError
from subphora.sources.national import InputParseError
from subphora.sources.sentinel import (
    Band,
    BandRead,
    BandReadError,
    Scene,
    ScenePage,
    SceneParseError,
    parse_scene_page,
    read_band,
    search_params,
)

_WEB_MERCATOR = "EPSG:3857"
# A search that keeps paging past this many pages is refused.
_MAX_PAGES = 200
# SIGPAC answers this for a tile without enclosures (docs/knowledge/sigpac.md).
_NO_TILE = 404


@dataclass(frozen=True, slots=True)
class VegetationInput:
    # One NDVI composite per Sentinel-2 tile, as GeoTIFF.
    composites: list[bytes]
    # The share of each cell of the window in irrigated enclosures (0-1).
    irrigated_share: FloatGrid
    # The summers composited, oldest first.
    summers: list[int]
    fetched: list[Fetched]


def select_scenes(
    scenes: Sequence[Scene], per_year: int, max_cloud_pct: float
) -> dict[str, dict[int, list[Scene]]]:
    """Per Sentinel-2 tile and year, its ``per_year`` least cloudy scenes under the limit
    (once each: a scene found by two searches counts once)."""
    unique = {scene.id: scene for scene in scenes if scene.cloud_pct <= max_cloud_pct}
    grouped: dict[str, dict[int, list[Scene]]] = defaultdict(lambda: defaultdict(list))
    for scene in unique.values():
        grouped[scene.tile][scene.acquired.year].append(scene)
    return {
        tile: {
            year: sorted(items, key=lambda s: (s.cloud_pct, s.id))[:per_year]
            for year, items in sorted(years.items())
        }
        for tile, years in sorted(grouped.items())
    }


# Reads one band of a scene at a cell size (``sources.sentinel.read_band``); tests swap
# in a synthetic one, since GDAL's range reader is not behind the mocked transport.
type BandReader = Callable[[CatalogueClient, Band, float, GdalResampling], BandRead]


def _scene_ndvi(
    client: CatalogueClient, scene: Scene, dataset: VegetationDataset, reader: BandReader
) -> tuple[FloatGrid, Affine, str]:
    bands = dataset.bands
    red = reader(client, scene.bands[bands.red], dataset.read_cell_m, GdalResampling.average)
    nir = reader(client, scene.bands[bands.nir], dataset.read_cell_m, GdalResampling.average)
    scl = reader(
        client, scene.bands[bands.scene_class], dataset.read_cell_m, GdalResampling.nearest
    )
    rows = min(red.data.shape[0], nir.data.shape[0], scl.data.shape[0])
    columns = min(red.data.shape[1], nir.data.shape[1], scl.data.shape[1])
    red_band, nir_band = scene.bands[bands.red], scene.bands[bands.nir]
    values = ndvi(
        red.data[:rows, :columns],
        nir.data[:rows, :columns],
        scl.data[:rows, :columns],
        (red_band.scale, nir_band.scale),
        (red_band.offset, nir_band.offset),
        red_band.nodata,
        dataset.valid_scene_classes,
    )
    return values, red.transform, red.crs


def tile_composite(
    client: CatalogueClient,
    years: dict[int, list[Scene]],
    dataset: VegetationDataset,
    reader: BandReader = read_band,
) -> bytes:
    """The NDVI composite of one Sentinel-2 tile's scenes, as GeoTIFF. Blocks."""
    summers: list[list[FloatGrid]] = []
    reference: tuple[Affine, str, tuple[int, ...]] | None = None
    for scenes in years.values():
        arrays = []
        for scene in scenes:
            values, transform, crs = _scene_ndvi(client, scene, dataset, reader)
            if reference is None:
                reference = (transform, crs, values.shape)
            shape = reference[2]
            fitted = np.full(shape, np.nan, dtype=np.float32)
            rows, columns = min(shape[0], values.shape[0]), min(shape[1], values.shape[1])
            fitted[:rows, :columns] = values[:rows, :columns]
            arrays.append(fitted)
        summers.append(arrays)
    if reference is None:
        raise ValueError("a tile composite needs at least one scene")
    transform, crs, _ = reference
    return write_geotiff(composite(summers, dataset.min_years), transform, crs)


def _composite_key(tile: str, years: dict[int, list[Scene]], dataset: VegetationDataset) -> str:
    recipe = [
        tile,
        f"cell={dataset.read_cell_m}",
        f"classes={sorted(dataset.valid_scene_classes)}",
        f"min_years={dataset.min_years}",
        *(scene.id for scenes in years.values() for scene in scenes),
    ]
    return "ndvi-composite:" + hashlib.sha256("|".join(recipe).encode()).hexdigest()


def _mask_key(mask: IrrigationMask, z: int, x: int, y: int) -> str:
    recipe = [
        mask.path.format(z=z, x=x, y=y),
        mask.layer,
        f"{mask.coefficient_field}>={mask.min_coefficient}",
        f"px={max(1, mask.raster_px >> (z - mask.zoom))}",
    ]
    return "irrigation-mask:" + hashlib.sha256("|".join(recipe).encode()).hexdigest()


class VegetationFetcher:
    def __init__(
        self, client: CatalogueClient, inputs: InputFetcher, reader: BandReader = read_band
    ) -> None:
        self._client = client
        self._inputs = inputs
        self._reader = reader

    async def _search(
        self, dataset: VegetationDataset, bbox: tuple[float, float, float, float], year: int
    ) -> tuple[list[Scene], list[Fetched]]:
        service = self._inputs.service(dataset.service)
        start, end = dataset.season.dates(year)
        bands = (dataset.bands.red, dataset.bands.nir, dataset.bands.scene_class)

        def parse(content: bytes) -> ScenePage:
            try:
                return parse_scene_page(content, bands)
            except SceneParseError as exc:
                raise InputParseError(str(exc)) from exc

        url: str | None = service.base_url + "/search"
        params = search_params(
            dataset.collection, bbox, start.isoformat(), end.isoformat(), dataset.page_size
        )
        scenes: list[Scene] = []
        fetched: list[Fetched] = []
        for _ in range(_MAX_PAGES):
            if url is None:
                return scenes, fetched
            answer: tuple[ScenePage, Fetched] = await self._inputs.get(service, url, params, parse)
            page, fetched_page = answer
            scenes.extend(page.scenes)
            fetched.append(fetched_page)
            url, params = page.next_url, {}
        raise InputFailure(f"{service.publisher}: more than {_MAX_PAGES} pages of scenes")

    async def _composite(
        self,
        tile: str,
        years: dict[int, list[Scene]],
        dataset: VegetationDataset,
        slots: asyncio.Semaphore,
    ) -> Fetched:
        service = self._inputs.service(dataset.pixels_service)
        key = _composite_key(tile, years, dataset)
        hit = await self._inputs.recall(service, key)
        if hit is not None:
            return hit
        async with slots:
            try:
                content = await asyncio.to_thread(
                    tile_composite, self._client, years, dataset, self._reader
                )
            except (BandReadError, HostNotAllowedError) as exc:
                raise InputFailure(f"{service.publisher}: {exc}") from exc
        return await self._inputs.remember(service, key, content)

    async def _irrigation(
        self, dataset: VegetationDataset, window: GridWindow
    ) -> tuple[FloatGrid, list[Fetched]]:
        mask = dataset.irrigation
        service = self._inputs.service(mask.service)
        box = lon_lat_bounds(buffered(window.bounds, dataset.neighbourhood_m), window.crs)
        share = np.zeros(window.shape, dtype=np.float32)
        tiles = tiles_covering(box, mask.zoom)

        def add(content: bytes) -> None:
            burnt = read_geotiff(content)
            warp_into(
                share,
                window,
                burnt.data,
                burnt.transform,
                burnt.crs,
                None,
                Resampling.average,
            )

        async def one(z: int, x: int, y: int) -> list[Fetched]:
            key = _mask_key(mask, z, x, y)
            hit = await self._inputs.recall(service, key)
            if hit is not None:
                if hit.content:
                    await asyncio.to_thread(add, hit.content)
                return [hit]
            url = service.base_url + mask.path.format(z=z, x=x, y=y)
            fetched = await self._inputs.fetch_or_empty(service, url, (_NO_TILE,))
            if not fetched.content and z < mask.deepest_zoom:
                await self._inputs.keep(service, fetched)
                # Some large tiles are not served (404) where their four children are.
                children = await asyncio.gather(
                    *(one(z + 1, 2 * x + dx, 2 * y + dy) for dx in (0, 1) for dy in (0, 1))
                )
                return [f for found in children for f in found]
            try:
                polygons = await asyncio.to_thread(
                    polygons_at_least,
                    fetched.content,
                    (z, x, y),
                    mask.layer,
                    mask.coefficient_field,
                    mask.min_coefficient,
                )
            except VectorTileError as exc:
                raise InputFailure(f"{service.publisher}: tile {z}/{x}/{y}: {exc}") from exc
            content = b""
            if polygons:
                size = max(1, mask.raster_px >> (z - mask.zoom))
                raster, transform = await asyncio.to_thread(
                    burn_box, tile_bounds(z, x, y), polygons, size
                )
                content = await asyncio.to_thread(write_geotiff, raster, transform, _WEB_MERCATOR)
                await asyncio.to_thread(add, content)
            # The tile's burnt raster (nothing irrigated: no bytes) stands for the tile.
            return [await self._inputs.remember(service, key, content)]

        found = await asyncio.gather(*(one(mask.zoom, x, y) for x, y in tiles))
        return share, [f for answers in found for f in answers]

    async def fetch(
        self, dataset: VegetationDataset, window: GridWindow, today: date
    ) -> VegetationInput:
        """The composites over the window and its irrigation share; raises InputFailure."""
        summers = dataset.season.summers(today, dataset.years)
        bbox = lon_lat_bounds(window.bounds, window.crs)
        searched = await asyncio.gather(*(self._search(dataset, bbox, year) for year in summers))
        scenes = [scene for found, _ in searched for scene in found]
        fetched = [answer for _, answers in searched for answer in answers]
        chosen = select_scenes(scenes, dataset.scenes_per_year, dataset.max_cloud_pct)
        slots = asyncio.Semaphore(
            self._inputs.service(dataset.pixels_service).politeness.max_concurrent
        )
        composites = await asyncio.gather(
            *(self._composite(tile, years, dataset, slots) for tile, years in chosen.items())
        )
        share, masks = await self._irrigation(dataset, window)
        return VegetationInput(
            composites=[c.content for c in composites],
            irrigated_share=share,
            summers=summers,
            fetched=[*fetched, *composites, *masks],
        )


__all__ = ["BandReader", "VegetationFetcher", "VegetationInput", "select_scenes", "tile_composite"]
