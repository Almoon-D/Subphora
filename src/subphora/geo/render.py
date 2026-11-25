# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Raster tiles of a national grid: a grid warped onto a Web Mercator tile and coloured by
classes into a palette PNG, transparent where the grid has no value."""

import io
from collections.abc import Sequence

import numpy as np
from affine import Affine
from numpy.typing import NDArray
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import reproject

from subphora.geo.tiles import tile_bounds

_WEB_MERCATOR = "EPSG:3857"


def tile_transform(z: int, x: int, y: int, size: int) -> Affine:
    west, _south, east, north = tile_bounds(z, x, y)
    pixel = (east - west) / size
    return Affine(pixel, 0.0, west, 0.0, -pixel, north)


def warp_onto_tile(
    target: NDArray[np.float32],
    data: NDArray[np.float32],
    transform: Affine,
    crs: str,
    z: int,
    x: int,
    y: int,
) -> None:
    """Draw a grid onto the tile in place, nearest cell; cells already drawn are kept where
    the grid has no value."""
    size = target.shape[0]
    reproject(
        source=data,
        destination=target,
        src_transform=transform,
        src_crs=crs,
        src_nodata=np.nan,
        dst_transform=tile_transform(z, x, y, size),
        dst_crs=_WEB_MERCATOR,
        dst_nodata=np.nan,
        init_dest_nodata=False,
        resampling=Resampling.nearest,
    )


def _rgb(colour: str) -> tuple[int, int, int]:
    return (int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16))


def colour_png(
    values: NDArray[np.float32], breaks: Sequence[float], colours: Sequence[str]
) -> bytes | None:
    """A palette PNG of the values by class; None when no pixel has a value."""
    valid = ~np.isnan(values)
    if not valid.any():
        return None
    transparent = len(colours)
    classes = np.digitize(np.nan_to_num(values, nan=0.0), list(breaks), right=False)
    indices = np.where(valid, classes, transparent).astype(np.uint8)
    height, width = indices.shape
    image = Image.frombytes("P", (width, height), indices.tobytes())
    palette = [channel for colour in colours for channel in _rgb(colour)] + [0, 0, 0]
    image.putpalette(palette)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", transparency=transparent, optimize=True)
    return buffer.getvalue()


def transparent_png(size: int) -> bytes:
    """A fully transparent tile, for a place inside the map's bounds with no value."""
    image = Image.new("LA", (size, size), (0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
