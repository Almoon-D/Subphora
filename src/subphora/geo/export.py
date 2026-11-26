# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Files a GIS opens: Cloud-Optimised GeoTIFFs of grids and GeoPackage layers of features,
each with its CRS declared (MASTER_PLAN §4.6, the export pack).

GDAL writes both (through rasterio and pyogrio); this module only turns our grids and
GeoJSON-like geometries into what it takes. The functions block.
"""

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyogrio.raw
import rasterio
import rasterio.shutil
from affine import Affine
from numpy.typing import NDArray

# WKB geometry types (ISO), little-endian.
_WKB_POINT = 1
_WKB_POLYGON = 3
_LITTLE_ENDIAN = 1

type FieldValue = str | float | int | None


def write_cog(
    path: Path,
    bands: Mapping[str, NDArray[np.float32]],
    transform: Affine,
    crs: str,
    blocksize: int,
    compress: str,
) -> None:
    """The bands, named by their keys, as one Cloud-Optimised GeoTIFF (NaN: no value)."""
    first = next(iter(bands.values()))
    height, width = first.shape
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": len(bands),
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": float("nan"),
    }
    with rasterio.MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            for index, (name, band) in enumerate(bands.items(), start=1):
                dataset.write(np.asarray(band, dtype=np.float32), index)
                dataset.set_band_description(index, name)
        with memory.open() as source:
            rasterio.shutil.copy(
                source,
                path,
                driver="COG",
                BLOCKSIZE=blocksize,
                COMPRESS=compress.upper(),
                PREDICTOR="FLOATING_POINT",
                OVERVIEW_RESAMPLING="NEAREST",
            )


def _point(x: float, y: float) -> bytes:
    return struct.pack("<BIdd", _LITTLE_ENDIAN, _WKB_POINT, x, y)


def _polygon(rings: Sequence[Sequence[Sequence[float]]]) -> bytes:
    parts = [struct.pack("<BII", _LITTLE_ENDIAN, _WKB_POLYGON, len(rings))]
    for ring in rings:
        parts.append(struct.pack("<I", len(ring)))
        parts.extend(struct.pack("<dd", float(p[0]), float(p[1])) for p in ring)
    return b"".join(parts)


@dataclass(frozen=True, slots=True)
class VectorLayer:
    """One GeoPackage layer: its name, geometry type, and features as (geometry, fields).
    A point geometry is (x, y); a polygon, GeoJSON rings."""

    name: str
    geometry_type: Literal["Point", "Polygon"]
    fields: tuple[str, ...]
    features: tuple[tuple[Any, Mapping[str, FieldValue]], ...]


def _column(values: list[FieldValue]) -> NDArray[Any]:
    present = [v for v in values if v is not None]
    if present and all(isinstance(v, float | int) and not isinstance(v, bool) for v in present):
        if all(isinstance(v, int) for v in present) and len(present) == len(values):
            return np.array(values, dtype=np.int64)
        return np.array([np.nan if v is None else float(v) for v in values], dtype=np.float64)
    return np.array([None if v is None else str(v) for v in values], dtype=object)


def write_gpkg(path: Path, layers: Sequence[VectorLayer], crs: str) -> None:
    """Every layer into one GeoPackage in ``crs``; a layer with no feature is still
    written, empty, so its absence is never mistaken for a missing layer."""
    path.unlink(missing_ok=True)
    for index, layer in enumerate(layers):
        encode = _point if layer.geometry_type == "Point" else None
        geometries = np.array(
            [
                encode(*geometry) if encode is not None else _polygon(geometry)
                for geometry, _ in layer.features
            ],
            dtype=object,
        )
        columns = [
            _column([fields.get(name) for _, fields in layer.features]) for name in layer.fields
        ]
        pyogrio.raw.write(
            path,
            geometries,
            columns,
            list(layer.fields),
            layer=layer.name,
            driver="GPKG",
            geometry_type=layer.geometry_type,
            crs=crs,
            append=index > 0,
        )


__all__ = ["FieldValue", "VectorLayer", "write_cog", "write_gpkg"]
