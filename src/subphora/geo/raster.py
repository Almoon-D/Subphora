# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Inputs onto a grid window: polygons burnt in, rasters warped in, distances to features.

Raster warping is GDAL's (through rasterio): a grid is resampled by its own algorithms,
never by hand. Every grid is float, NaN where it has no value.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
from affine import Affine
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.warp import reproject
from scipy.ndimage import distance_transform_edt
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree

from subphora.geo.grid import GridWindow

type FloatGrid = NDArray[np.float32]
# A GeoJSON geometry mapping, already in the window's CRS.
type Geometry = dict[str, Any]


class RasterReadError(ValueError):
    """Bytes that are not a readable georeferenced raster."""


@dataclass(frozen=True, slots=True)
class Raster:
    data: NDArray[Any]
    transform: Affine
    crs: str
    nodata: float | None


def read_geotiff(content: bytes) -> Raster:
    """The first band of a GeoTIFF held in memory; raises RasterReadError."""
    try:
        with MemoryFile(content) as memory, memory.open() as dataset:
            if dataset.crs is None:
                raise RasterReadError("the raster has no CRS")
            return Raster(
                data=np.asarray(dataset.read(1)),
                transform=dataset.transform,
                crs=str(dataset.crs),
                nodata=None if dataset.nodata is None else float(dataset.nodata),
            )
    except RasterioIOError as exc:
        raise RasterReadError(f"not a readable raster: {exc}") from exc


def empty(window: GridWindow) -> FloatGrid:
    return np.full(window.shape, np.nan, dtype=np.float32)


def burn(window: GridWindow, shapes: Sequence[tuple[Geometry, float]], fill: float) -> FloatGrid:
    """Polygons burnt in with their values, later ones over earlier ones; ``fill`` where no
    polygon covers a cell's centre."""
    if not shapes:
        return np.full(window.shape, fill, dtype=np.float32)
    result = rasterize(
        shapes,
        out_shape=window.shape,
        transform=window.transform,
        fill=fill,
        dtype="float32",
        all_touched=False,
    )
    return np.asarray(result, dtype=np.float32)


def warp_into(
    target: FloatGrid,
    window: GridWindow,
    source: NDArray[Any],
    source_transform: Affine,
    source_crs: str,
    source_nodata: float | None,
    resampling: Resampling,
) -> None:
    """Resample ``source`` onto ``target`` in place: cells the source covers are replaced,
    the others are kept (so windows of a larger source add up)."""
    data = np.asarray(source, dtype=np.float32)
    if source_nodata is not None:
        data = np.where(data == source_nodata, np.nan, data)
    reproject(
        source=data,
        destination=target,
        src_transform=source_transform,
        src_crs=source_crs,
        src_nodata=np.nan,
        dst_transform=window.transform,
        dst_crs=window.crs,
        dst_nodata=np.nan,
        init_dest_nodata=False,
        resampling=resampling,
    )


def points_mask(window: GridWindow, points: Iterable[tuple[float, float]]) -> NDArray[np.bool_]:
    """The cells that hold at least one of the points (in the window's CRS)."""
    mask = np.zeros(window.shape, dtype=bool)
    for x, y in points:
        cell = window.cell_of(x, y)
        if cell is not None:
            mask[cell] = True
    return mask


def distance_to(mask: NDArray[np.bool_], cell_m: float, cap_m: float) -> FloatGrid:
    """Metres from each cell to the nearest cell of ``mask``, at most ``cap_m``: the cap
    where none is that near, or the window holds none."""
    if not mask.any():
        return np.full(mask.shape, cap_m, dtype=np.float32)
    distance = np.asarray(distance_transform_edt(~mask), dtype=np.float64) * cell_m
    return np.minimum(distance, cap_m).astype(np.float32)


def _cell_centres(window: GridWindow) -> NDArray[np.float64]:
    """Every cell's centre (x, y) in the window's CRS, row by row."""
    columns = window.west + (np.arange(window.width) + 0.5) * window.cell_m
    rows = window.north - (np.arange(window.height) + 0.5) * window.cell_m
    xs, ys = np.meshgrid(columns, rows)
    return np.column_stack((xs.ravel(), ys.ravel()))


def distance_to_points(
    window: GridWindow, points: Sequence[tuple[float, float]], cap_m: float
) -> FloatGrid:
    """Metres from each cell's centre to the nearest point (in the window's CRS, inside the
    window or not), at most ``cap_m``: the cap where none is that near."""
    if not points:
        return np.full(window.shape, cap_m, dtype=np.float32)
    distance, _ = cKDTree(np.asarray(points, dtype=np.float64)).query(
        _cell_centres(window), distance_upper_bound=cap_m
    )
    return np.minimum(np.asarray(distance), cap_m).reshape(window.shape).astype(np.float32)


def nearest_value(
    window: GridWindow,
    points: Sequence[tuple[float, float]],
    values: Sequence[float],
    max_distance_m: float,
) -> FloatGrid:
    """Each cell takes the value of the nearest point within ``max_distance_m``; NaN where
    none is that near."""
    if not points:
        return empty(window)
    distance, nearest = cKDTree(np.asarray(points, dtype=np.float64)).query(
        _cell_centres(window), distance_upper_bound=max_distance_m
    )
    found = np.isfinite(distance)
    table = np.append(np.asarray(values, dtype=np.float64), np.nan)
    result = np.where(found, table[np.where(found, nearest, len(values))], np.nan)
    grid: FloatGrid = result.reshape(window.shape).astype(np.float32)
    return grid


def line_density(
    window: GridWindow, lines: Iterable[Sequence[tuple[float, float]]], radius_m: float
) -> FloatGrid:
    """Kilometres of line within ``radius_m`` of each cell's centre, per km² of that circle.

    Each line is cut into pieces no longer than half a cell, and each piece's length is
    counted in the cell holding its middle; the sums are then added over a disc of cells.
    Cells nearer than ``radius_m`` to the window's edge miss the lines beyond it.
    """
    lengths = np.zeros(window.shape, dtype=np.float64)
    step = window.cell_m / 2
    for line in lines:
        vertices = np.asarray(line, dtype=np.float64)
        if vertices.ndim != 2 or len(vertices) < 2:
            continue
        for (x0, y0), (x1, y1) in pairwise(vertices):
            length = float(np.hypot(x1 - x0, y1 - y0))
            if length == 0:
                continue
            pieces = max(1, int(np.ceil(length / step)))
            middles = (np.arange(pieces) + 0.5) / pieces
            xs = x0 + (x1 - x0) * middles
            ys = y0 + (y1 - y0) * middles
            columns = np.floor((xs - window.west) / window.cell_m).astype(np.int64)
            rows = np.floor((window.north - ys) / window.cell_m).astype(np.int64)
            keep = (rows >= 0) & (rows < window.height) & (columns >= 0) & (columns < window.width)
            np.add.at(lengths, (rows[keep], columns[keep]), length / pieces)
    reach = int(radius_m // window.cell_m)
    offsets = np.arange(-reach, reach + 1) * window.cell_m
    disc = (np.hypot(*np.meshgrid(offsets, offsets)) <= radius_m).astype(np.float64)
    disc_km2 = disc.sum() * window.cell_m**2 / 1e6
    total = np.clip(np.asarray(fftconvolve(lengths, disc, mode="same")), 0.0, None)
    density: FloatGrid = (total / 1000 / disc_km2).astype(np.float32)
    return density


__all__ = [
    "FloatGrid",
    "Geometry",
    "Raster",
    "RasterReadError",
    "Resampling",
    "burn",
    "distance_to",
    "distance_to_points",
    "empty",
    "line_density",
    "nearest_value",
    "points_mask",
    "read_geotiff",
    "warp_into",
]
