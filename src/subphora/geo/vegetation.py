# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The late-summer vegetation anomaly from Sentinel-2 L2A bands (decision 0041).

- NDVI = (NIR - red) / (NIR + red) on surface reflectance (the digital numbers times the
  scale plus the offset the catalogue states), only where the scene classification is a
  valid class and both bands have data; NaN elsewhere.
- A tile's composite: the median NDVI of each summer's scenes, then the median over the
  summers, only where at least ``min_years`` summers have a value. A pixel cloudy in one
  scene of a summer takes that summer's other scenes.
- The anomaly: a cell's composite minus the mean composite of the land that is not
  irrigated within a radius. Irrigated cells, and cells with no such land around, are NaN:
  never filled in.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.signal import fftconvolve

from subphora.geo.raster import FloatGrid

# Neighbourhood sums below this (cells) are rounding noise of the convolution.
_NOISE = 1e-6


def ndvi(
    red: NDArray[Any],
    nir: NDArray[Any],
    scene_class: NDArray[Any],
    scale: tuple[float, float],
    offset: tuple[float, float],
    nodata: float,
    valid_classes: Sequence[int],
) -> FloatGrid:
    """NDVI from the red and NIR digital numbers; ``scale`` and ``offset`` per band (red,
    NIR) turn them into reflectance."""
    red_dn = np.asarray(red, dtype=np.float64)
    nir_dn = np.asarray(nir, dtype=np.float64)
    r = red_dn * scale[0] + offset[0]
    n = nir_dn * scale[1] + offset[1]
    total = n + r
    valid = (
        np.isin(np.asarray(scene_class), list(valid_classes))
        & (red_dn != nodata)
        & (nir_dn != nodata)
        & (r >= 0)
        & (n >= 0)
        & (total > 0)
    )
    safe = np.where(valid, total, 1.0)
    result: FloatGrid = np.where(valid, (n - r) / safe, np.nan).astype(np.float32)
    return result


def _nanmedian(stack: Sequence[FloatGrid]) -> FloatGrid:
    data = np.stack([np.asarray(a, dtype=np.float32) for a in stack])
    count = np.sum(~np.isnan(data), axis=0)
    filled = np.where(np.isnan(data), np.inf, data)
    ordered = np.sort(filled, axis=0)
    low = np.clip((count - 1) // 2, 0, None)
    high = np.clip(count // 2, 0, None)
    lower = np.take_along_axis(ordered, low[None], axis=0)[0]
    upper = np.take_along_axis(ordered, high[None], axis=0)[0]
    median: FloatGrid = np.where(count > 0, (lower + upper) / 2, np.nan).astype(np.float32)
    return median


def composite(summers: Sequence[Sequence[FloatGrid]], min_years: int) -> FloatGrid:
    """The median over the summers of each summer's median scene; NaN where fewer than
    ``min_years`` summers have a value. Every array has the same shape."""
    yearly = [_nanmedian(scenes) for scenes in summers if scenes]
    if not yearly:
        raise ValueError("a composite needs at least one scene")
    overall = _nanmedian(yearly)
    years = np.sum(~np.isnan(np.stack(yearly)), axis=0)
    result: FloatGrid = np.where(years >= min_years, overall, np.nan).astype(np.float32)
    return result


def _disc(radius_m: float, cell_m: float) -> NDArray[np.float64]:
    reach = int(radius_m // cell_m)
    offsets = np.arange(-reach, reach + 1) * cell_m
    disc: NDArray[np.float64] = (np.hypot(*np.meshgrid(offsets, offsets)) <= radius_m).astype(
        np.float64
    )
    return disc


def anomaly(
    values: FloatGrid, irrigated: NDArray[np.bool_], cell_m: float, radius_m: float
) -> FloatGrid:
    """Each cell's value minus the mean over the non-irrigated cells with a value within
    ``radius_m`` (a disc of cells); NaN where irrigated, without a value, or alone."""
    data = np.asarray(values, dtype=np.float64)
    kept = ~np.isnan(data) & ~np.asarray(irrigated, dtype=bool)
    disc = _disc(radius_m, cell_m)
    sums = np.asarray(fftconvolve(np.where(kept, data, 0.0), disc, mode="same"))
    counts = np.asarray(fftconvolve(kept.astype(np.float64), disc, mode="same"))
    has_reference = counts > 1 - _NOISE
    mean = np.where(has_reference, sums / np.where(has_reference, counts, 1.0), np.nan)
    result: FloatGrid = np.where(kept & has_reference, data - mean, np.nan).astype(np.float32)
    return result


__all__ = ["anomaly", "composite", "ndvi"]
