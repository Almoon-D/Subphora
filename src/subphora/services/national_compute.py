# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The CPU work of the national build, run in worker processes: one region's grids from its
downloaded inputs, and batches of tiles from the regions' grids.

Each job carries everything it needs (settings, downloaded bytes, paths) and returns a
small result, so it pickles to a worker and back. Nothing here touches the network.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import ClassesLookup, ModelSettings
from subphora.config.national import (
    VARIABLE_DATASET,
    GroundwaterBodiesDataset,
    NationalSettings,
    PermeabilityDataset,
    WaterPointsDataset,
)
from subphora.domain.potential import InputSource, Variable
from subphora.geo.grid import GridWindow, transform_bounds, transform_geometry
from subphora.geo.raster import (
    FloatGrid,
    Geometry,
    Resampling,
    burn,
    distance_to,
    empty,
    points_mask,
    read_geotiff,
    warp_into,
)
from subphora.geo.render import colour_png, warp_onto_tile
from subphora.geo.terrain import derive
from subphora.geo.tiles import tile_bounds
from subphora.model.evaluate import ABSENT, Category, InputGrids, Quality, evaluate
from subphora.model.quality import dataset_quality
from subphora.store.national import Category as StoredCategory
from subphora.store.national import (
    CriterionQuality,
    RegionManifest,
    read_decimated,
    write_region,
)

_LON_LAT = "EPSG:4326"
_WEB_MERCATOR = "EPSG:3857"
_INSIDE = 1.0


@dataclass(frozen=True, slots=True)
class RegionInputs:
    """One region's downloaded inputs, as their services answered them."""

    # The region's boundary in EPSG:4326, or None for a bbox region (the box itself).
    boundary: list[Geometry] | None
    # Permeability polygons and water points in the grid's CRS; bodies in their ``srs``.
    permeability: list[dict[str, Any]]
    terrain: list[bytes]
    soil: list[bytes]
    groundwater_bodies: list[dict[str, Any]]
    water_points: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RegionJob:
    root: Path
    region_id: str
    name: str
    grid_id: str
    window: GridWindow
    bbox: tuple[float, float, float, float]
    built_at: datetime
    national: NationalSettings
    model: ModelSettings
    metres_per_scale_unit: float
    # Per dataset: where and when it was read.
    sources: dict[str, InputSource]
    inputs: RegionInputs


@dataclass(frozen=True, slots=True)
class RegionResult:
    region_id: str
    cells: int
    scored: int


def _region_mask(job: RegionJob) -> NDArray[np.bool_]:
    window = job.window
    if job.inputs.boundary is None:
        west, south, east, north = job.bbox
        ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
        shapes: list[Geometry] = [{"type": "Polygon", "coordinates": [ring]}]
    else:
        shapes = job.inputs.boundary
    projected = [(transform_geometry(s, _LON_LAT, window.crs), _INSIDE) for s in shapes]
    inside: NDArray[np.bool_] = burn(window, projected, fill=0.0) == _INSIDE
    return inside


def _categorical(
    window: GridWindow,
    features: Sequence[dict[str, Any]],
    key: Any,
    order: Any,
    source_crs: str,
) -> tuple[FloatGrid, list[Category]]:
    """Burn features as codes into their category list; ``key`` gives a feature's
    (class, label) or None, ``order`` a category's drawing rank (later wins)."""
    categories: list[Category] = []
    codes: dict[Category, int] = {}
    shapes: list[tuple[Geometry, Category]] = []
    for feature in features:
        geometry = feature.get("geometry")
        found = key(feature.get("properties") or {})
        if found is None or not isinstance(geometry, dict):
            continue
        category = Category(cls=found[0], label=found[1])
        if category not in codes:
            codes[category] = len(categories)
            categories.append(category)
        if source_crs != window.crs:
            geometry = transform_geometry(geometry, source_crs, window.crs)
        shapes.append((geometry, category))
    shapes.sort(key=lambda shape: order(shape[1]))
    burnt = burn(window, [(g, float(codes[c])) for g, c in shapes], fill=float(ABSENT))
    return burnt, categories


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def permeability_grid(
    window: GridWindow, features: Sequence[dict[str, Any]], dataset: PermeabilityDataset
) -> tuple[FloatGrid, list[Category]]:
    """Permeability polygons (in the window's CRS) burnt as class codes."""

    def key(properties: dict[str, Any]) -> tuple[str, str] | None:
        cls = _text(properties.get(dataset.class_field))
        return (cls, _text(properties.get(dataset.label_field))) if cls else None

    return _categorical(window, features, key, lambda _c: 0, window.crs)


def groundwater_grid(
    window: GridWindow,
    features: Sequence[dict[str, Any]],
    dataset: GroundwaterBodiesDataset,
    model: ModelSettings,
) -> tuple[FloatGrid, list[Category]]:
    """Groundwater bodies (in the dataset's ``srs``) burnt as status codes."""
    lookup = _classes_of(model, Variable.GROUNDWATER_STATUS)

    def key(properties: dict[str, Any]) -> tuple[str, str]:
        name = _text(properties.get(dataset.name_field))
        code = _text(properties.get(dataset.code_field))
        return (_text(properties.get(dataset.status_field)), f"{name} ({code})")

    def order(category: Category) -> float:
        # Where bodies overlap (horizons), the least suitable status is drawn last and
        # wins; a status the lookup does not list is drawn first.
        suitability = lookup.get(category.cls) if lookup else None
        return 2.0 if suitability is None else -suitability

    return _categorical(window, features, key, order, dataset.srs)


def _classes_of(model: ModelSettings, variable: Variable) -> dict[str, float] | None:
    for criterion in model.criteria:
        if criterion.variable is variable and isinstance(criterion.lookup, ClassesLookup):
            return criterion.lookup.classes
    return None


def warped(
    window: GridWindow, tiffs: Sequence[bytes], nodata: float, resampling: Resampling
) -> FloatGrid:
    """GeoTIFF windows of one raster resampled onto the grid; NaN where none covers it."""
    grid = empty(window)
    for content in tiffs:
        raster = read_geotiff(content)
        warp_into(grid, window, raster.data, raster.transform, raster.crs, nodata, resampling)
    return grid


def water_point_positions(
    features: Sequence[dict[str, Any]], dataset: WaterPointsDataset
) -> list[tuple[float, float]]:
    """The water points' positions, without the kinds that are not groundwater."""
    excluded = set(dataset.exclude_kinds)
    points = []
    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if _text(properties.get(dataset.kind_field)) in excluded:
            continue
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            points.append((float(coordinates[0]), float(coordinates[1])))
    return points


def _water_points(job: RegionJob) -> FloatGrid:
    points = water_point_positions(job.inputs.water_points, job.national.datasets.water_points)
    mask = points_mask(job.window, points)
    return distance_to(mask, job.window.cell_m, job.national.buffer_m)


def _quality(job: RegionJob) -> dict[str, Quality]:
    settings = job.model.confidence
    result = {}
    for criterion in job.model.criteria:
        # No nationwide input for it (the faults and dips of the parcel scale, or none).
        if criterion.variable not in VARIABLE_DATASET:
            continue
        dataset = job.national.datasets.all()[VARIABLE_DATASET[criterion.variable]]
        result[criterion.id] = dataset_quality(
            dataset.detail,
            job.window.cell_m,
            job.metres_per_scale_unit,
            job.built_at.year,
            settings.ageing[dataset.ageing],
            settings.unknown_value,
        )
    return result


def compute_region(job: RegionJob) -> RegionResult:
    """Every grid of one region, scored and written to its stack and manifest."""
    window = job.window
    datasets = job.national.datasets
    permeability, permeability_categories = permeability_grid(
        window, job.inputs.permeability, datasets.permeability
    )
    groundwater, groundwater_categories = groundwater_grid(
        window, job.inputs.groundwater_bodies, datasets.groundwater_bodies, job.model
    )
    elevation = warped(
        window, job.inputs.terrain, float(datasets.terrain.sea_value), Resampling.average
    )
    terrain = derive(
        elevation,
        window,
        datasets.terrain.channel_area_km2,
        datasets.terrain.min_slope_deg,
        job.national.buffer_m,
    )
    clay = warped(window, job.inputs.soil, float(datasets.soil.nodata_value), Resampling.nearest)
    grids: dict[Variable, FloatGrid] = {
        Variable.PERMEABILITY_CLASS: permeability,
        Variable.ELEVATION_M: elevation,
        Variable.SLOPE_DEG: terrain.slope_deg,
        Variable.TWI: terrain.twi,
        Variable.DRAINAGE_DISTANCE_M: terrain.drainage_distance_m,
        Variable.CLAY_PCT: (clay * datasets.soil.scale).astype(np.float32),
        Variable.GROUNDWATER_STATUS: groundwater,
        Variable.WATER_POINT_DISTANCE_M: _water_points(job),
    }
    mask = _region_mask(job)
    grids = {v: np.where(mask, g, np.nan).astype(np.float32) for v, g in grids.items()}
    categories = {
        Variable.PERMEABILITY_CLASS: permeability_categories,
        Variable.GROUNDWATER_STATUS: groundwater_categories,
    }
    quality = _quality(job)
    evaluation = evaluate(
        job.model,
        InputGrids(values=grids, categories=categories),
        quality,
        grids[Variable.WATER_POINT_DISTANCE_M],
    )
    grids[Variable.INDEX] = evaluation.index.astype(np.float32)
    grids[Variable.CONFIDENCE] = evaluation.confidence.astype(np.float32)
    criterion_sources = {
        c.id: job.sources[VARIABLE_DATASET[c.variable]]
        for c in job.model.criteria
        if c.variable in VARIABLE_DATASET
    }
    manifest = RegionManifest(
        region_id=job.region_id,
        name=job.name,
        grid=job.grid_id,
        crs=window.crs,
        cell_m=window.cell_m,
        west=window.west,
        north=window.north,
        width=window.width,
        height=window.height,
        bbox=job.bbox,
        built_at=job.built_at,
        bands=tuple(grids),
        categories={
            v: tuple(StoredCategory(cls=c.cls, label=c.label) for c in items)
            for v, items in categories.items()
        },
        sources=criterion_sources,
        quality={
            k: CriterionQuality(resolution=q.resolution, age=q.age) for k, q in quality.items()
        },
        distance_cap_m=job.national.buffer_m,
        model=job.model,
    )
    write_region(job.root, manifest, dict(grids))
    return RegionResult(
        region_id=job.region_id,
        cells=int(mask.sum()),
        scored=int((~np.isnan(grids[Variable.INDEX])).sum()),
    )


@dataclass(frozen=True, slots=True)
class TileJob:
    root: Path
    manifests: tuple[RegionManifest, ...]
    variable: Variable
    breaks: tuple[float, ...]
    colours: tuple[str, ...]
    tile_size: int
    tiles: tuple[tuple[int, int, int], ...]


def render_tiles(job: TileJob) -> list[tuple[int, int, int, bytes]]:
    """The PNG of every tile of the batch that has a value; tiles without one are left out."""
    rendered = []
    for z, x, y in job.tiles:
        target = np.full((job.tile_size, job.tile_size), np.nan, dtype=np.float32)
        box = tile_bounds(z, x, y)
        lon_lat = transform_bounds(box, _WEB_MERCATOR, _LON_LAT)
        for manifest in job.manifests:
            if not _overlaps(manifest.bbox, lon_lat):
                continue
            bounds = transform_bounds(box, _WEB_MERCATOR, manifest.crs)
            cell = (bounds[2] - bounds[0]) / job.tile_size
            read = read_decimated(job.root, manifest, job.variable, bounds, cell)
            if read is None:
                continue
            data, transform = read
            warp_onto_tile(target, data, transform, manifest.crs, z, x, y)
        png = colour_png(target, job.breaks, job.colours)
        if png is not None:
            rendered.append((z, x, y, png))
    return rendered


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
