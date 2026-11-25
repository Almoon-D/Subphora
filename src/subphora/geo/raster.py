# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Inputs onto a grid window: polygons burnt in, rasters warped in, distances to features.

Raster warping is GDAL's (through rasterio): a grid is resampled by its own algorithms,
never by hand. Every grid is float, NaN where it has no value.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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


__all__ = [
    "FloatGrid",
    "Geometry",
    "Raster",
    "RasterReadError",
    "Resampling",
    "burn",
    "distance_to",
    "empty",
    "points_mask",
    "read_geotiff",
    "warp_into",
]
