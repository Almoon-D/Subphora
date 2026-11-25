# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The detailed maps of areas on disk, one per area id (MASTER_PLAN §4.3, parcel scale).

Layout under the jobs' output directory (git-ignored, hard rule 6):

- ``regions/<id>.tif`` and ``regions/<id>.json``: the area's grid stack and its manifest,
  in the national build's format (``store.national``), so a cell is explained the same way.
- ``images/<id>/<layer>.png``: each published layer as one Web Mercator image.
- ``analyses/<id>.json``: the area's analysis (summary and candidates). It is written
  last, so an area without one was never finished and is computed again.

Every file is written to a temporary name and renamed into place. The functions block.
"""

from pathlib import Path

from subphora.domain.parcel_map import AreaAnalysis
from subphora.store.national import write_bytes, write_json

_ANALYSES = "analyses"
_IMAGES = "images"


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
    "image_path",
    "read_analysis",
    "write_analysis",
    "write_image",
]
