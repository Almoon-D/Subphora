# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The national map on disk: one grid stack per build region, and one PMTiles archive per
published layer (MASTER_PLAN §4.3).

Layout under the build's output directory:

- ``regions/<region>.tif``: every variable of the region as one float32 band, named by
  the variable, NaN outside the region and where there is no value; deflate, tiled, with
  averaged overviews for the tiles of the lower zooms.
- ``regions/<region>.json``: the region's manifest. It is written last, so a region
  without one was never finished and is ignored.
- ``tiles/<layer>.pmtiles``: the layer's PNG tiles over every region built.

Every file is written to a temporary name and renamed into place, so a reader never sees
half of one. The functions block: async callers run them in a thread or a process.
"""

import os
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Annotated, Any, BinaryIO

import numpy as np
import rasterio
from numpy.typing import NDArray
from pmtiles.reader import MmapSource, Reader
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from pydantic import AwareDatetime, Field
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from subphora.config.model import ModelSettings
from subphora.domain import DomainModel
from subphora.domain.potential import DISTANCES, InputSource, Variable

type Bounds = tuple[float, float, float, float]

_REGIONS = "regions"
_TILES = "tiles"
_OVERVIEW_FACTORS = [2, 4, 8, 16, 32, 64]
_BLOCK = 256


class Category(DomainModel):
    cls: str
    label: str


class CriterionQuality(DomainModel):
    resolution: float = Field(ge=0, le=1)
    age: float = Field(ge=0, le=1)


class RegionManifest(DomainModel):
    """What a region's grid holds and how it was made: enough to explain any cell exactly
    as the build scored it, with the model settings of that build."""

    region_id: str
    name: str
    grid: str
    crs: str
    cell_m: float = Field(gt=0)
    # The window's north-west corner and size, in the grid's CRS.
    west: float
    north: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    # West, south, east, north in degrees.
    bbox: Bounds
    built_at: AwareDatetime
    bands: tuple[Variable, ...]
    categories: dict[Variable, tuple[Category, ...]]
    # Per criterion with an input: its source, and how its resolution and age fit.
    sources: dict[str, InputSource]
    quality: dict[str, CriterionQuality]
    # Distances are reported as "at least" this, unless ``distance_caps`` has their own.
    distance_cap_m: float = Field(gt=0)
    model: ModelSettings
    distance_caps: dict[Variable, Annotated[float, Field(gt=0)]] = Field(default_factory=dict)

    def caps(self) -> dict[Variable, float]:
        """Every distance variable's cap."""
        return {v: self.distance_caps.get(v, self.distance_cap_m) for v in DISTANCES}


class RegionSummary(DomainModel):
    region_id: str
    name: str
    grid: str
    bbox: Bounds
    built_at: AwareDatetime


class MapManifest(DomainModel):
    """``map.json``: the regions the published tiles cover, and when they were rendered."""

    rendered_at: AwareDatetime
    regions: tuple[RegionSummary, ...]
    # West, south, east, north in degrees, enclosing every region.
    bounds: Bounds
    # The layers with an archive, and how many tiles each holds.
    tiles: dict[str, int]


_MAP = "map.json"


def map_path(root: Path) -> Path:
    return root / _MAP


def read_map(root: Path) -> MapManifest | None:
    """The published map, or None before the first build; raises ValueError if unreadable."""
    try:
        content = map_path(root).read_bytes()
    except FileNotFoundError:
        return None
    return MapManifest.model_validate_json(content)


def regions_dir(root: Path) -> Path:
    return root / _REGIONS


def tiles_path(root: Path, layer_id: str) -> Path:
    return root / _TILES / f"{layer_id}.pmtiles"


def _temporary(folder: Path, suffix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=folder, prefix=".tmp-", suffix=suffix)
    os.close(fd)
    return Path(name)


def write_region(
    root: Path, manifest: RegionManifest, grids: dict[Variable, NDArray[np.floating]]
) -> None:
    """The region's grid stack, then its manifest (the commit)."""
    folder = regions_dir(root)
    if set(grids) != set(manifest.bands):
        raise ValueError("the manifest names exactly the bands written")
    tif = _temporary(folder, ".tif")
    try:
        profile = {
            "driver": "GTiff",
            "width": manifest.width,
            "height": manifest.height,
            "count": len(manifest.bands),
            "dtype": "float32",
            "crs": manifest.crs,
            "transform": rasterio.Affine(
                manifest.cell_m, 0.0, manifest.west, 0.0, -manifest.cell_m, manifest.north
            ),
            "nodata": float("nan"),
            "compress": "deflate",
            "predictor": 3,
            "tiled": True,
            "blockxsize": _BLOCK,
            "blockysize": _BLOCK,
            "BIGTIFF": "IF_SAFER",
        }
        with rasterio.open(tif, "w", **profile) as dataset:
            for index, variable in enumerate(manifest.bands, start=1):
                dataset.write(np.asarray(grids[variable], dtype=np.float32), index)
                dataset.set_band_description(index, variable.value)
            factors = [f for f in _OVERVIEW_FACTORS if f < max(manifest.width, manifest.height)]
            if factors:
                dataset.build_overviews(factors, Resampling.average)
        tif.replace(folder / f"{manifest.region_id}.tif")
    except BaseException:
        tif.unlink(missing_ok=True)
        raise
    write_bytes(folder / f"{manifest.region_id}.json", manifest.model_dump_json().encode())


def write_bytes(path: Path, content: bytes) -> None:
    tmp = _temporary(path.parent, path.suffix)
    try:
        tmp.write_bytes(content)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_manifests(root: Path) -> list[RegionManifest]:
    """Every finished region, by id; raises ValueError for a manifest that cannot be read."""
    folder = regions_dir(root)
    if not folder.is_dir():
        return []
    manifests = []
    for path in sorted(folder.glob("*.json")):
        if not (folder / f"{path.stem}.tif").exists():
            continue
        try:
            manifests.append(RegionManifest.model_validate_json(path.read_bytes()))
        except ValueError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    return manifests


def read_manifest(root: Path, region_id: str) -> RegionManifest | None:
    """One finished region, or None; raises ValueError for one that cannot be read."""
    folder = regions_dir(root)
    path = folder / f"{region_id}.json"
    if not path.exists() or not (folder / f"{region_id}.tif").exists():
        return None
    try:
        return RegionManifest.model_validate_json(path.read_bytes())
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def region_tif(root: Path, region_id: str) -> Path:
    return regions_dir(root) / f"{region_id}.tif"


def read_cell(root: Path, manifest: RegionManifest, row: int, column: int) -> dict[Variable, float]:
    """Every band's value at one cell of the region."""
    window = rasterio.windows.Window(column, row, 1, 1)
    with rasterio.open(region_tif(root, manifest.region_id)) as dataset:
        values = dataset.read(window=window)
    return {variable: float(values[index, 0, 0]) for index, variable in enumerate(manifest.bands)}


def read_decimated(
    root: Path,
    manifest: RegionManifest,
    variable: Variable,
    bounds: Bounds,
    target_cell_m: float,
) -> tuple[NDArray[np.float32], rasterio.Affine] | None:
    """The band over ``bounds`` (grid CRS), averaged to about ``target_cell_m`` cells (the
    overviews serve it), with its transform; None when the region does not reach there."""
    band = manifest.bands.index(variable) + 1
    with rasterio.open(region_tif(root, manifest.region_id)) as dataset:
        window = from_bounds(*bounds, transform=dataset.transform)
        window = window.intersection(rasterio.windows.Window(0, 0, dataset.width, dataset.height))
        window = window.round_offsets().round_lengths()
        if window.width < 1 or window.height < 1:
            return None
        factor = max(1, int(target_cell_m // manifest.cell_m))
        height = max(1, int(window.height) // factor)
        width = max(1, int(window.width) // factor)
        data = dataset.read(
            band, window=window, out_shape=(height, width), resampling=Resampling.average
        )
        transform = dataset.window_transform(window) @ rasterio.Affine.scale(
            window.width / width, window.height / height
        )
    return np.asarray(data, dtype=np.float32), transform


def write_tiles(
    path: Path,
    tiles: Iterable[tuple[int, int, int, bytes]],
    bounds: Bounds,
    metadata: dict[str, Any],
) -> int:
    """A PMTiles archive of PNG tiles (z, x, y, png); returns how many were written."""
    ordered = sorted((zxy_to_tileid(z, x, y), z, png) for z, x, y, png in tiles)
    if not ordered:
        path.unlink(missing_ok=True)
        return 0
    tmp = _temporary(path.parent, ".pmtiles")
    try:
        with tmp.open("wb") as handle:
            # pmtiles declares no types for its writer and reader.
            writer = Writer(handle)  # type: ignore[no-untyped-call]
            for tile_id, _z, png in ordered:
                writer.write_tile(tile_id, png)  # type: ignore[no-untyped-call]
            west, south, east, north = bounds
            zooms = [z for _, z, _ in ordered]
            writer.finalize(  # type: ignore[no-untyped-call]
                {
                    "tile_type": TileType.PNG,
                    "tile_compression": Compression.NONE,
                    "min_zoom": min(zooms),
                    "max_zoom": max(zooms),
                    "min_lon_e7": int(west * 1e7),
                    "min_lat_e7": int(south * 1e7),
                    "max_lon_e7": int(east * 1e7),
                    "max_lat_e7": int(north * 1e7),
                    "center_zoom": min(zooms),
                    "center_lon_e7": int((west + east) / 2 * 1e7),
                    "center_lat_e7": int((south + north) / 2 * 1e7),
                },
                metadata,
            )
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return len(ordered)


class TileArchive:
    """Reads tiles from a PMTiles archive; reopens it when the build replaces the file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._stamp: int | None = None
        self._handle: BinaryIO | None = None
        self._get: Callable[[int, int, int], bytes | None] | None = None

    def get(self, z: int, x: int, y: int) -> bytes | None:
        """The tile, or None when the archive or the tile does not exist."""
        try:
            stamp = self._path.stat().st_mtime_ns
        except FileNotFoundError:
            self.close()
            return None
        if self._get is None or stamp != self._stamp:
            self.close()
            self._handle = self._path.open("rb")
            reader = Reader(MmapSource(self._handle))  # type: ignore[no-untyped-call]
            self._get = reader.get
            self._stamp = stamp
        return self._get(z, x, y)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
        self._handle = None
        self._get = None
        self._stamp = None


def write_json(path: Path, body: DomainModel) -> None:
    write_bytes(path, body.model_dump_json(indent=2).encode())


def manifest_categories(
    categories: dict[Variable, Sequence[tuple[str, str]]],
) -> dict[Variable, tuple[Category, ...]]:
    return {
        variable: tuple(Category(cls=cls, label=label) for cls, label in items)
        for variable, items in categories.items()
    }


__all__ = [
    "Category",
    "CriterionQuality",
    "MapManifest",
    "RegionManifest",
    "RegionSummary",
    "TileArchive",
    "manifest_categories",
    "map_path",
    "read_cell",
    "read_decimated",
    "read_manifest",
    "read_manifests",
    "read_map",
    "region_tif",
    "regions_dir",
    "tiles_path",
    "write_bytes",
    "write_json",
    "write_region",
    "write_tiles",
]
