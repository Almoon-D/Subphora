# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The CPU work of an area's detailed map, run in a worker process: its grids from the
downloaded inputs, scored by the model, its candidates and means, and its map images.

The job carries everything it needs (settings, downloaded bytes and features, paths) and
returns the finished analysis, so it pickles to a worker and back. Nothing here touches
the network. The grids are computed over the area's window (area plus buffer), then kept
only inside the area: what lies in the buffer is there for flow and distances, not
scored, explained or drawn.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import ModelSettings
from subphora.config.national import NationalSettings, TileLayer
from subphora.config.parcel import ParcelSettings
from subphora.domain.layers import LayerDetail
from subphora.domain.legal import LegalState, LegalStatus
from subphora.domain.parcel_map import (
    AreaAnalysis,
    AreaSummary,
    Candidate,
    CriterionSummary,
    NoCandidates,
)
from subphora.domain.parcels import LocalPoint
from subphora.domain.potential import (
    CATEGORICAL,
    InputSource,
    MissingInput,
    MissingReason,
    Variable,
)
from subphora.geo.grid import GridWindow, lon_lat_bounds, transform_xy
from subphora.geo.raster import (
    FloatGrid,
    Geometry,
    Resampling,
    burn,
    distance_to_points,
    line_density,
    nearest_value,
)
from subphora.geo.render import overlay_image
from subphora.geo.terrain import derive
from subphora.model import (
    Category,
    Evaluation,
    InputGrids,
    Quality,
    area_means,
    confidence_of,
    dataset_quality,
    evaluate,
    explain_cell,
    select_candidates,
)
from subphora.services.national_compute import (
    groundwater_grid,
    permeability_grid,
    warped,
    water_point_positions,
)
from subphora.store.national import Category as StoredCategory
from subphora.store.national import CriterionQuality, RegionManifest, write_region
from subphora.store.parcels import write_analysis, write_image

_LON_LAT = "EPSG:4326"
_INSIDE = 1.0

# The dataset each input variable is read from on the detailed map.
PARCEL_VARIABLE_DATASET: dict[Variable, str] = {
    Variable.PERMEABILITY_CLASS: "permeability",
    Variable.ELEVATION_M: "terrain",
    Variable.SLOPE_DEG: "terrain",
    Variable.TWI: "terrain",
    Variable.DRAINAGE_DISTANCE_M: "terrain",
    Variable.CLAY_PCT: "soil",
    Variable.GROUNDWATER_STATUS: "groundwater_bodies",
    Variable.WATER_POINT_DISTANCE_M: "water_points",
    Variable.LINEAMENT_DENSITY: "faults",
    Variable.BEDDING_DIP_DEG: "bedding",
}


@dataclass(frozen=True, slots=True)
class ParcelInputs:
    """An area's downloaded inputs, as their services answered them: features in the
    window's CRS (groundwater bodies in their dataset's ``srs``), rasters as GeoTIFFs."""

    permeability: list[dict[str, Any]]
    terrain: list[bytes]
    soil: list[bytes]
    groundwater_bodies: list[dict[str, Any]]
    water_points: list[dict[str, Any]]
    faults: list[dict[str, Any]]
    bedding: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ParcelJobSpec:
    root: Path
    area_id: str
    label: str | None
    # The area's outline in the window's CRS (a point's disc), and its size.
    area: list[Geometry]
    area_m2: float
    window: GridWindow
    built_at: datetime
    parcel: ParcelSettings
    national: NationalSettings
    model: ModelSettings
    metres_per_scale_unit: float
    # Per dataset (PARCEL_VARIABLE_DATASET's values): where and when it was read.
    sources: dict[str, InputSource]
    inputs: ParcelInputs


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lines(geometry: Any) -> list[list[tuple[float, float]]]:
    """The vertex lists of a GeoJSON LineString or MultiLineString; none otherwise."""
    if not isinstance(geometry, dict):
        return []
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return []
    parts = {"LineString": [coordinates], "MultiLineString": coordinates}.get(
        str(geometry.get("type")), []
    )
    return [
        [(float(p[0]), float(p[1])) for p in part if isinstance(p, list) and len(p) >= 2]
        for part in parts
        if isinstance(part, list)
    ]


def fault_lines(spec: ParcelJobSpec) -> list[list[tuple[float, float]]]:
    faults = spec.parcel.faults
    lines = []
    for feature in spec.inputs.faults:
        kind = _text((feature.get("properties") or {}).get(faults.type_field))
        if faults.is_fault(kind):
            lines.extend(_lines(feature.get("geometry")))
    return lines


def bedding_dips(spec: ParcelJobSpec) -> tuple[list[tuple[float, float]], list[float]]:
    """The bedding measurements' positions (the middle of each symbol's line) and dips;
    a measurement without a dip is left out."""
    bedding = spec.parcel.bedding
    kinds = set(bedding.kinds)
    positions: list[tuple[float, float]] = []
    dips: list[float] = []
    for feature in spec.inputs.bedding:
        properties = feature.get("properties") or {}
        dip = properties.get(bedding.dip_field)
        if _text(properties.get(bedding.kind_field)) not in kinds or not isinstance(
            dip, int | float
        ):
            continue
        for line in _lines(feature.get("geometry"))[:1]:
            if line:
                (x0, y0), (x1, y1) = line[0], line[-1]
                positions.append(((x0 + x1) / 2, (y0 + y1) / 2))
                dips.append(float(dip))
    return positions, dips


def _details(spec: ParcelJobSpec) -> dict[str, tuple[LayerDetail, str]]:
    """Per dataset: its stated detail and ageing profile."""
    national = spec.national.datasets
    parcel = spec.parcel
    return {
        "permeability": (national.permeability.detail, national.permeability.ageing),
        "terrain": (parcel.terrain.detail, parcel.terrain.ageing),
        "soil": (national.soil.detail, national.soil.ageing),
        "groundwater_bodies": (
            national.groundwater_bodies.detail,
            national.groundwater_bodies.ageing,
        ),
        "water_points": (national.water_points.detail, national.water_points.ageing),
        "faults": (parcel.faults.detail, parcel.faults.ageing),
        "bedding": (parcel.bedding.detail, parcel.bedding.ageing),
    }


def _quality(spec: ParcelJobSpec) -> dict[str, Quality]:
    settings = spec.model.confidence
    details = _details(spec)
    result = {}
    for criterion in spec.model.criteria:
        if criterion.variable not in PARCEL_VARIABLE_DATASET:
            continue
        detail, ageing = details[PARCEL_VARIABLE_DATASET[criterion.variable]]
        result[criterion.id] = dataset_quality(
            detail,
            spec.window.cell_m,
            spec.metres_per_scale_unit,
            spec.built_at.year,
            settings.ageing[ageing],
            settings.unknown_value,
        )
    return result


def _grids(spec: ParcelJobSpec) -> tuple[dict[Variable, FloatGrid], dict[Variable, list[Category]]]:
    """Every input variable over the whole window."""
    window = spec.window
    national = spec.national.datasets
    parcel = spec.parcel
    permeability, permeability_categories = permeability_grid(
        window, spec.inputs.permeability, national.permeability
    )
    groundwater, groundwater_categories = groundwater_grid(
        window, spec.inputs.groundwater_bodies, national.groundwater_bodies, spec.model
    )
    elevation = warped(
        window, spec.inputs.terrain, float(national.terrain.sea_value), Resampling.bilinear
    )
    terrain = derive(
        elevation,
        window,
        national.terrain.channel_area_km2,
        national.terrain.min_slope_deg,
        parcel.buffer_m,
    )
    clay = warped(window, spec.inputs.soil, float(national.soil.nodata_value), Resampling.nearest)
    positions, dips = bedding_dips(spec)
    grids: dict[Variable, FloatGrid] = {
        Variable.PERMEABILITY_CLASS: permeability,
        Variable.ELEVATION_M: elevation,
        Variable.SLOPE_DEG: terrain.slope_deg,
        Variable.TWI: terrain.twi,
        Variable.DRAINAGE_DISTANCE_M: terrain.drainage_distance_m,
        Variable.CLAY_PCT: (clay * national.soil.scale).astype(np.float32),
        Variable.GROUNDWATER_STATUS: groundwater,
        Variable.WATER_POINT_DISTANCE_M: distance_to_points(
            window,
            water_point_positions(spec.inputs.water_points, national.water_points),
            parcel.water_points_radius_m,
        ),
        Variable.LINEAMENT_DENSITY: line_density(window, fault_lines(spec), parcel.faults.radius_m),
        Variable.BEDDING_DIP_DEG: nearest_value(
            window, positions, dips, parcel.bedding.max_distance_m
        ),
    }
    categories = {
        Variable.PERMEABILITY_CLASS: permeability_categories,
        Variable.GROUNDWATER_STATUS: groundwater_categories,
    }
    return grids, categories


def _crop(window: GridWindow, inside: NDArray[np.bool_]) -> tuple[GridWindow, tuple[slice, slice]]:
    """The smallest window of the grid holding every cell of the area."""
    rows = np.flatnonzero(inside.any(axis=1))
    columns = np.flatnonzero(inside.any(axis=0))
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(columns[0]), int(columns[-1]) + 1
    cropped = GridWindow(
        crs=window.crs,
        cell_m=window.cell_m,
        west=window.west + left * window.cell_m,
        north=window.north - top * window.cell_m,
        width=right - left,
        height=bottom - top,
    )
    return cropped, (slice(top, bottom), slice(left, right))


class EmptyAreaError(ValueError):
    """The area holds no cell centre of the grid."""


def compute_parcel(spec: ParcelJobSpec) -> AreaAnalysis:
    """The area's grids, analysis and images, written under ``spec.root``."""
    inside_window = burn(spec.window, [(g, _INSIDE) for g in spec.area], fill=0.0) == _INSIDE
    if not inside_window.any():
        raise EmptyAreaError("the area holds no cell of the grid")
    window, view = _crop(spec.window, inside_window)
    inside = inside_window[view]
    full, categories = _grids(spec)
    grids = {v: np.where(inside, g[view], np.nan).astype(np.float32) for v, g in full.items()}
    quality = _quality(spec)
    evaluation = evaluate(
        spec.model,
        InputGrids(values=grids, categories=categories),
        quality,
        grids[Variable.WATER_POINT_DISTANCE_M],
    )
    grids[Variable.INDEX] = evaluation.index.astype(np.float32)
    grids[Variable.CONFIDENCE] = evaluation.confidence.astype(np.float32)
    sources = {
        c.id: spec.sources[PARCEL_VARIABLE_DATASET[c.variable]]
        for c in spec.model.criteria
        if c.variable in PARCEL_VARIABLE_DATASET
    }
    caps = {
        Variable.DRAINAGE_DISTANCE_M: spec.parcel.buffer_m,
        Variable.WATER_POINT_DISTANCE_M: spec.parcel.water_points_radius_m,
    }
    manifest = RegionManifest(
        region_id=spec.area_id,
        name=spec.label or spec.area_id,
        grid="parcel",
        crs=window.crs,
        cell_m=window.cell_m,
        west=window.west,
        north=window.north,
        width=window.width,
        height=window.height,
        bbox=_lon_lat_box(window),
        built_at=spec.built_at,
        bands=tuple(grids),
        categories={
            v: tuple(StoredCategory(cls=c.cls, label=c.label) for c in items)
            for v, items in categories.items()
        },
        sources=sources,
        quality={
            k: CriterionQuality(resolution=q.resolution, age=q.age) for k, q in quality.items()
        },
        distance_cap_m=max(caps.values()),
        distance_caps=caps,
        model=spec.model,
    )
    write_region(spec.root, manifest, dict(grids))
    layers = [spec.national.tiles.layer(layer_id) for layer_id in spec.parcel.layers]
    corners = _write_images(spec, window, grids, layers)
    candidates, no_candidates = _candidates(spec, window, grids, inside, categories, quality)
    analysis = AreaAnalysis(
        id=spec.area_id,
        label=spec.label,
        crs=window.crs,
        cell_m=window.cell_m,
        bbox=corners,
        area_m2=spec.area_m2,
        built_at=spec.built_at,
        layers=tuple(layer.variable for layer in layers),
        summary=_summary(spec, evaluation, inside, sources),
        candidates=candidates,
        no_candidates=no_candidates,
        sources=spec.sources,
        terrain_model=spec.parcel.terrain.model,
    )
    write_analysis(spec.root, analysis)
    return analysis


def _lon_lat_box(window: GridWindow) -> tuple[float, float, float, float]:
    return lon_lat_bounds(window.bounds, window.crs)


def _write_images(
    spec: ParcelJobSpec,
    window: GridWindow,
    grids: dict[Variable, FloatGrid],
    layers: Sequence[TileLayer],
) -> tuple[float, float, float, float]:
    corners = _lon_lat_box(window)
    for layer in layers:
        png, corners = overlay_image(
            grids[layer.variable],
            window.transform,
            window.crs,
            layer.breaks,
            layer.colours,
            spec.parcel.image_max_px,
        )
        if png is not None:
            write_image(spec.root, spec.area_id, layer.id, png)
    return corners


def _candidates(
    spec: ParcelJobSpec,
    window: GridWindow,
    grids: dict[Variable, FloatGrid],
    inside: NDArray[np.bool_],
    categories: dict[Variable, list[Category]],
    quality: dict[str, Quality],
) -> tuple[tuple[Candidate, ...], NoCandidates | None]:
    settings = spec.parcel.candidates
    index = grids[Variable.INDEX]
    cells = select_candidates(
        index,
        grids[Variable.CONFIDENCE],
        inside,
        window.cell_m,
        settings.count,
        settings.min_confidence,
        settings.min_separation_m,
    )
    if not cells:
        scored = bool((inside & ~np.isnan(index)).any())
        return (), NoCandidates.LOW_CONFIDENCE if scored else NoCandidates.NO_SCORE
    legal = LegalStatus(
        state=LegalState.NOT_EVALUATED,
        source=spec.parcel.legal.not_evaluated_source,
        assessed_at=spec.built_at,
        disclaimer=spec.parcel.legal.disclaimer,
    )
    sources = {
        c.id: spec.sources[PARCEL_VARIABLE_DATASET[c.variable]]
        for c in spec.model.criteria
        if c.variable in PARCEL_VARIABLE_DATASET
    }
    caps = {
        Variable.DRAINAGE_DISTANCE_M: spec.parcel.buffer_m,
        Variable.WATER_POINT_DISTANCE_M: spec.parcel.water_points_radius_m,
    }
    candidates = []
    for rank, (row, column) in enumerate(cells, start=1):
        x = window.west + (column + 0.5) * window.cell_m
        y = window.north - (row + 0.5) * window.cell_m
        lon, lat = transform_xy(x, y, window.crs, _LON_LAT)
        values: dict[Variable, float] = {
            v: float(g[row, column])
            for v, g in grids.items()
            if v not in (Variable.INDEX, Variable.CONFIDENCE)
        }
        estimate = explain_cell(
            spec.model,
            values,
            {v: items for v, items in categories.items() if v in CATEGORICAL},
            quality,
            sources,
            values[Variable.WATER_POINT_DISTANCE_M],
            caps,
        )
        candidates.append(
            Candidate(
                rank=rank,
                longitude=lon,
                latitude=lat,
                local=LocalPoint(crs=window.crs, x=x, y=y),
                estimate=estimate,
                legal=legal,
            )
        )
    return tuple(candidates), None


def _summary(
    spec: ParcelJobSpec,
    evaluation: Evaluation,
    inside: NDArray[np.bool_],
    sources: dict[str, InputSource],
) -> AreaSummary:
    means = area_means(spec.model, evaluation, inside)
    contributions = tuple(
        CriterionSummary(
            criterion=c.id,
            weight=c.weight,
            mean_share=means.criteria[c.id].mean_share,
            mean_contribution=means.criteria[c.id].mean_contribution,
            present_share=means.criteria[c.id].present_share,
            source=sources[c.id],
        )
        for c in spec.model.criteria
        if c.id in means.criteria
    )
    missing = tuple(
        MissingInput(
            criterion=c.id,
            weight=c.weight,
            reason=MissingReason.NO_DATASET
            if c.variable not in PARCEL_VARIABLE_DATASET
            else MissingReason.NO_DATA,
        )
        for c in spec.model.criteria
        if c.id not in means.criteria
    )
    return AreaSummary(
        cells=means.cells,
        scored_cells=means.scored_cells,
        mean_index=means.mean_index,
        mean_confidence=None
        if means.mean_confidence is None
        else confidence_of(means.components, spec.model.confidence),
        contributions=contributions,
        missing=missing,
    )
