# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The detailed maps of areas on disk, one per area id (MASTER_PLAN §4.3, parcel scale).

Layout under the jobs' output directory (git-ignored, hard rule 6):

- ``regions/<id>.tif`` and ``regions/<id>.json``: the area's grid stack and its manifest,
  in the national build's format (``store.national``), so a cell is explained the same way.
- ``images/<id>/<layer>.png``: each published layer as one Web Mercator image.
- ``outlines/<id>.json``: the area analysed (its polygons, or the disc around a point) in
  the grid's CRS, as GeoJSON geometries.
- ``depth/<id>.tif``: the depth to water and its range over the grid (bands ``depth_m``,
  ``low_m``, ``high_m``; NaN where unknown); only when piezometric levels were imported.
- ``analyses/<id>.json``: the area's analysis (summary and candidates). It is written
  last, so an area without one was never finished and is computed again.

Every file is written to a temporary name and renamed into place. The functions block.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from numpy.typing import NDArray

from subphora.domain.parcel_map import AreaAnalysis
from subphora.store.national import write_bytes, write_json

_ANALYSES = "analyses"
_IMAGES = "images"
_OUTLINES = "outlines"
_DEPTH = "depth"


def outline_path(root: Path, area_id: str) -> Path:
    return root / _OUTLINES / f"{area_id}.json"


def write_outline(root: Path, area_id: str, polygons: list[dict[str, Any]]) -> None:
    write_bytes(outline_path(root, area_id), json.dumps(polygons).encode())


def read_outline(root: Path, area_id: str) -> list[dict[str, Any]] | None:
    """The area's polygons in the grid's CRS, or None; raises ValueError when unreadable."""
    path = outline_path(root, area_id)
    try:
        polygons = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc
    if not isinstance(polygons, list) or not all(
        isinstance(p, dict) and p.get("type") == "Polygon" for p in polygons
    ):
        raise ValueError(f"{path.name}: not a list of polygons")
    return polygons


def depth_path(root: Path, area_id: str) -> Path:
    return root / _DEPTH / f"{area_id}.tif"


def write_depth(
    root: Path,
    area_id: str,
    crs: str,
    transform: rasterio.Affine,
    bands: Mapping[str, NDArray[np.float32]],
) -> None:
    path = depth_path(root, area_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = next(iter(bands.values()))
    temporary = path.with_name(f".tmp-{path.name}")
    try:
        with rasterio.open(
            temporary,
            "w",
            driver="GTiff",
            width=first.shape[1],
            height=first.shape[0],
            count=len(bands),
            dtype="float32",
            crs=crs,
            transform=transform,
            nodata=float("nan"),
            compress="deflate",
        ) as dataset:
            for index, (name, band) in enumerate(bands.items(), start=1):
                dataset.write(np.asarray(band, dtype=np.float32), index)
                dataset.set_band_description(index, name)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def analysis_path(root: Path, area_id: str) -> Path:
    return root / _ANALYSES / f"{area_id}.json"


def image_path(root: Path, area_id: str, layer_id: str) -> Path:
    return root / _IMAGES / area_id / f"{layer_id}.png"


def write_image(root: Path, area_id: str, layer_id: str, png: bytes) -> None:
    write_bytes(image_path(root, area_id, layer_id), png)


def write_analysis(root: Path, analysis: AreaAnalysis) -> None:
    """The commit: the area is finished once this is written."""
    write_json(analysis_path(root, analysis.id), analysis)


def read_analysis(root: Path, area_id: str) -> AreaAnalysis | None:
    """The finished analysis, or None; raises ValueError for one that cannot be read."""
    path = analysis_path(root, area_id)
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        return AreaAnalysis.model_validate_json(content)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


__all__ = [
    "analysis_path",
    "depth_path",
    "image_path",
    "outline_path",
    "read_analysis",
    "read_outline",
    "write_analysis",
    "write_depth",
    "write_image",
    "write_outline",
]
