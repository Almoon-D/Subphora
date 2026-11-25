# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Raster images of a grid: a national grid warped onto a Web Mercator tile, or a detailed
grid onto one Web Mercator image of its own extent, coloured by classes into a palette
PNG, transparent where the grid has no value."""

import io
from collections.abc import Sequence

import numpy as np
from affine import Affine
from numpy.typing import NDArray
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds

from subphora.geo.tiles import tile_bounds

_WEB_MERCATOR = "EPSG:3857"
_LON_LAT = "EPSG:4326"


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


def overlay_image(
    data: NDArray[np.float32],
    transform: Affine,
    crs: str,
    breaks: Sequence[float],
    colours: Sequence[str],
    max_px: int,
) -> tuple[bytes | None, tuple[float, float, float, float]]:
    """The grid as one Web Mercator PNG (nearest cell), at most ``max_px`` on its longer
    side, and its corners in degrees (west, south, east, north): a map draws it there
    without distortion, its rows and columns being Mercator's. None when no cell has a
    value."""
    height, width = data.shape
    west = transform.c
    north = transform.f
    east = west + width * transform.a
    south = north + height * transform.e
    target_transform, target_width, target_height = calculate_default_transform(
        crs, _WEB_MERCATOR, width, height, west, south, east, north
    )
    scale = max(1.0, max(target_width, target_height) / max_px)
    target_width = max(1, round(target_width / scale))
    target_height = max(1, round(target_height / scale))
    left, top = target_transform.c, target_transform.f
    right = left + target_transform.a * target_width * scale
    bottom = top + target_transform.e * target_height * scale
    pixel_x = (right - left) / target_width
    pixel_y = (top - bottom) / target_height
    target = np.full((target_height, target_width), np.nan, dtype=np.float32)
    reproject(
        source=np.asarray(data, dtype=np.float32),
        destination=target,
        src_transform=transform,
        src_crs=crs,
        src_nodata=np.nan,
        dst_transform=Affine(pixel_x, 0.0, left, 0.0, -pixel_y, top),
        dst_crs=_WEB_MERCATOR,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    lon_west, lat_south, lon_east, lat_north = transform_bounds(
        _WEB_MERCATOR, _LON_LAT, left, bottom, right, top
    )
    corners = (float(lon_west), float(lat_south), float(lon_east), float(lat_north))
    return colour_png(target, breaks, colours), corners
