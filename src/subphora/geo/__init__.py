# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Coordinates: reprojection with pyproj, bounding boxes, outlines, Web Mercator tiles."""

from subphora.geo.reproject import ReprojectionError, bbox_of, to_lon_lat, transform_point
from subphora.geo.shapes import ShapeError, check_simple_ring, geodesic_area_m2, point_inside
from subphora.geo.tiles import (
    MAX_TILE_ZOOM,
    MercatorBox,
    box_around,
    metres_per_pixel,
    reproject_box,
    tile_bounds,
    tile_exists,
)

__all__ = [
    "MAX_TILE_ZOOM",
    "MercatorBox",
    "ReprojectionError",
    "ShapeError",
    "bbox_of",
    "box_around",
    "check_simple_ring",
    "geodesic_area_m2",
    "metres_per_pixel",
    "point_inside",
    "reproject_box",
    "tile_bounds",
    "tile_exists",
    "to_lon_lat",
    "transform_point",
]
