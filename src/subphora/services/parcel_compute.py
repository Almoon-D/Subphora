# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The CPU work of an area's detailed map, run in a worker process: its grids from the
downloaded inputs, scored by the model, its candidates and means, and its map images.

The job carries everything it needs (settings, downloaded bytes and features, paths) and
returns the finished analysis, so it pickles to a worker and back. Nothing here touches
the network. The grids are computed over the area's window (area plus buffer), then kept
only inside the area: what lies in the buffer is there for flow and distances, not
scored, explained or drawn.

The skill of each domain comes from the national map's validation (the area is far too
small to validate on its own); each candidate gets its depth to water from the imported
piezometers of its own groundwater body, and the drilling cost of that depth.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from subphora.config.depth import DrillingSettings, PiezometrySettings
from subphora.config.model import ModelSettings
from subphora.config.national import NationalSettings, TileLayer
from subphora.config.parcel import ParcelSettings
from subphora.domain.depth import LevelsSource
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
    AUXILIARY,
    CATEGORICAL,
    RESULTS,
    InputSource,
    MissingInput,
    MissingReason,
    Variable,
)
from subphora.domain.validation import MEASURED, NO_BODY, DomainValidation
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
    PiezometerPoint,
    Quality,
    area_means,
    confidence_of,
    dataset_quality,
    depth_at,
    drilling_cost,
    evaluate,
    explain_cell,
    select_candidates,
)
from subphora.services.national_compute import (
    body_grid,
    groundwater_grid,
    permeability_grid,
    warped,
    water_point_positions,
)
from subphora.services.validation import domain_codes, domain_keys, domain_validations, skill_grid
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
    piezometry: PiezometrySettings
    drilling: DrillingSettings
    metres_per_scale_unit: float
    # Per dataset (PARCEL_VARIABLE_DATASET's values): where and when it was read.
    sources: dict[str, InputSource]
    inputs: ParcelInputs
    # The national map's validation per domain (body code, or the outside) near the area.
    validations: dict[str, DomainValidation]
    # The imported piezometers near the area, in the window's CRS, and the sources of
    # their levels by service (None when no levels were imported).
    piezometers: list[PiezometerPoint]
    levels: dict[str, LevelsSource] | None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def line_vertices(geometry: Any) -> list[list[tuple[float, float]]]:
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
            lines.extend(line_vertices(feature.get("geometry")))
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
        for line in line_vertices(feature.get("geometry"))[:1]:
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
    body, body_categories = body_grid(
        window, spec.inputs.groundwater_bodies, national.groundwater_bodies, spec.model
    )
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
        Variable.GROUNDWATER_BODY: body,
    }
    categories = {
        Variable.PERMEABILITY_CLASS: permeability_categories,
        Variable.GROUNDWATER_STATUS: groundwater_categories,
        Variable.GROUNDWATER_BODY: body_categories,
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
    body_categories = categories[Variable.GROUNDWATER_BODY]
    validations = domain_validations(body_categories, spec.validations)
    by_domain = {v.domain: v for v in validations}
    skill = skill_grid(grids[Variable.GROUNDWATER_BODY], body_categories, by_domain, spec.model)
    evaluation = evaluate(
        spec.model,
        InputGrids(values=grids, categories=categories),
        quality,
        grids[Variable.WATER_POINT_DISTANCE_M],
        skill,
    )
    grids[Variable.INDEX] = evaluation.index.astype(np.float32)
    grids[Variable.CONFIDENCE] = evaluation.confidence.astype(np.float32)
    grids[Variable.SKILL] = np.where(np.isnan(evaluation.index), np.nan, skill).astype(np.float32)
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
        validation=validations,
    )
    write_region(spec.root, manifest, dict(grids))
    layers = [spec.national.tiles.layer(layer_id) for layer_id in spec.parcel.layers]
    corners = _write_images(spec, window, grids, layers)
    candidates, no_candidates = _candidates(
        spec, window, grids, inside, categories, quality, by_domain
    )
    analysis = AreaAnalysis(
        id=spec.area_id,
        label=spec.label,
        crs=window.crs,
        cell_m=window.cell_m,
        bbox=corners,
        area_m2=spec.area_m2,
        built_at=spec.built_at,
        layers=tuple(layer.variable for layer in layers),
        summary=_summary(spec, evaluation, inside, sources, grids, body_categories, by_domain),
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
    validations: dict[str, DomainValidation],
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
            v: float(g[row, column]) for v, g in grids.items() if v not in RESULTS | AUXILIARY
        }
        body = _category_at(
            grids[Variable.GROUNDWATER_BODY], categories[Variable.GROUNDWATER_BODY], row, column
        )
        domain = NO_BODY if body is None else body.cls
        estimate = explain_cell(
            spec.model,
            values,
            {v: items for v, items in categories.items() if v in CATEGORICAL},
            quality,
            sources,
            values[Variable.WATER_POINT_DISTANCE_M],
            caps,
            validations[domain],
        )
        permeability = _category_at(
            grids[Variable.PERMEABILITY_CLASS], categories[Variable.PERMEABILITY_CLASS], row, column
        )
        depth = depth_at(
            x,
            y,
            values[Variable.ELEVATION_M],
            None if body is None else (body.cls, body.label),
            spec.piezometers,
            spec.piezometry.water_table,
            permeability is not None and spec.piezometry.is_karst(permeability.label),
            spec.levels,
        )
        candidates.append(
            Candidate(
                rank=rank,
                longitude=lon,
                latitude=lat,
                local=LocalPoint(crs=window.crs, x=x, y=y),
                estimate=estimate,
                legal=legal,
                depth=depth,
                cost=drilling_cost(depth, spec.drilling),
            )
        )
    return tuple(candidates), None


def _category_at(grid: FloatGrid, items: list[Category], row: int, column: int) -> Category | None:
    """The category of a categorical grid at a cell, or None where it has no feature."""
    value = float(grid[row, column])
    code = -1 if np.isnan(value) else int(value)
    return items[code] if 0 <= code < len(items) else None


def _summary(
    spec: ParcelJobSpec,
    evaluation: Evaluation,
    inside: NDArray[np.bool_],
    sources: dict[str, InputSource],
    grids: dict[Variable, FloatGrid],
    body_categories: list[Category],
    validations: dict[str, DomainValidation],
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
    domains = domain_codes(grids[Variable.GROUNDWATER_BODY], body_categories)
    keys = domain_keys(body_categories)
    present = sorted({int(code) for code in np.unique(domains[inside])})
    touched = tuple(validations[keys[code][0]] for code in present)
    return AreaSummary(
        cells=means.cells,
        scored_cells=means.scored_cells,
        mean_index=means.mean_index,
        mean_confidence=None
        if means.mean_confidence is None
        else confidence_of(
            means.components,
            spec.model.confidence,
            skill_measured=any(v.state in MEASURED for v in touched),
        ),
        contributions=contributions,
        missing=missing,
        validation=touched,
    )
