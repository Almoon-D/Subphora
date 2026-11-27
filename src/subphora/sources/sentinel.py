# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Sentinel-2 L2A scenes: the STAC search answers, and reading a band's overview from its
cloud-optimised GeoTIFF (docs/knowledge/copernicus.md, decision 0041).

- A search page is a GeoJSON FeatureCollection of items; the next page is its ``next``
  link. Each item names its Sentinel-2 tile (``grid:code``), its cloud cover, and per
  band an asset with its URL and the scale and offset that turn digital numbers into
  reflectance (``raster:bands``).
- A band is read by GDAL's HTTP range reader at a coarser cell than its own, so GDAL reads
  the overview that fits and never the full-resolution pixels. Before GDAL opens a URL its
  host is checked against the catalogue like any request (hard rule 4), and GDAL sends the
  same generic User-Agent. Reading blocks: callers run it in a thread.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError

from subphora.sources.client import CatalogueClient


class SceneParseError(ValueError):
    """A search answer that is not the STAC page asked for."""


class BandReadError(Exception):
    """A band's file could not be read."""


@dataclass(frozen=True, slots=True)
class Band:
    href: str
    scale: float
    offset: float
    nodata: float


@dataclass(frozen=True, slots=True)
class Scene:
    id: str
    tile: str
    acquired: datetime
    cloud_pct: float
    bands: dict[str, Band]


@dataclass(frozen=True, slots=True)
class ScenePage:
    scenes: list[Scene]
    next_url: str | None


@dataclass(frozen=True, slots=True)
class BandRead:
    data: NDArray[Any]
    transform: Affine
    crs: str


def search_params(
    collection: str, bbox: tuple[float, float, float, float], start: str, end: str, limit: int
) -> dict[str, str]:
    """A STAC item search over ``bbox`` (degrees) between two ISO dates, inclusive."""
    west, south, east, north = bbox
    return {
        "collections": collection,
        "bbox": f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": str(limit),
    }


def _band(asset: Mapping[str, Any]) -> Band | None:
    href = asset.get("href")
    if not isinstance(href, str) or not href.startswith("https://"):
        return None
    raster = asset.get("raster:bands") or [{}]
    first = raster[0] if isinstance(raster, list) and raster else {}
    return Band(
        href=href,
        scale=float(first.get("scale", 1.0)),
        offset=float(first.get("offset", 0.0)),
        nodata=float(first.get("nodata", 0)),
    )


def _scene(item: Mapping[str, Any], wanted: tuple[str, ...]) -> Scene | None:
    properties = item.get("properties") or {}
    assets = item.get("assets") or {}
    tile = properties.get("grid:code")
    cloud = properties.get("eo:cloud_cover")
    when = properties.get("datetime")
    if not (isinstance(tile, str) and isinstance(cloud, int | float) and isinstance(when, str)):
        return None
    bands = {}
    for key in wanted:
        asset = assets.get(key)
        band = _band(asset) if isinstance(asset, dict) else None
        if band is None:
            return None
        bands[key] = band
    return Scene(
        id=str(item.get("id")),
        tile=tile,
        acquired=datetime.fromisoformat(when.replace("Z", "+00:00")),
        cloud_pct=float(cloud),
        bands=bands,
    )


def parse_scene_page(content: bytes, wanted: tuple[str, ...]) -> ScenePage:
    """The scenes of a search page that have every band in ``wanted``; raises
    SceneParseError for anything but a FeatureCollection."""
    try:
        page = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SceneParseError(f"not JSON: {exc}") from exc
    if not isinstance(page, dict) or page.get("type") != "FeatureCollection":
        raise SceneParseError("not a STAC FeatureCollection")
    scenes = []
    for item in page.get("features") or []:
        if isinstance(item, dict):
            scene = _scene(item, wanted)
            if scene is not None:
                scenes.append(scene)
    next_url = None
    for link in page.get("links") or []:
        if (
            isinstance(link, dict)
            and link.get("rel") == "next"
            and link.get("method", "GET") == "GET"
        ):
            href = link.get("href")
            next_url = href if isinstance(href, str) else None
    return ScenePage(scenes=scenes, next_url=next_url)


def read_band(
    client: CatalogueClient, band: Band, cell_m: float, resampling: Resampling
) -> BandRead:
    """The whole band at ``cell_m`` (GDAL picks the overview); raises BandReadError or
    HostNotAllowedError. Blocks."""
    client.ensure_allowed(httpx.URL(band.href))
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_USERAGENT": client.user_agent,
        "GDAL_HTTP_MAX_RETRY": "2",
        "GDAL_HTTP_RETRY_DELAY": "3",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    try:
        with rasterio.Env(**options), rasterio.open("/vsicurl/" + band.href) as dataset:
            if dataset.crs is None:
                raise BandReadError(f"{band.href}: no CRS")
            native = abs(dataset.transform.a)
            factor = max(1.0, cell_m / native)
            height = max(1, math.ceil(dataset.height / factor))
            width = max(1, math.ceil(dataset.width / factor))
            data = dataset.read(1, out_shape=(height, width), resampling=resampling)
            transform = dataset.transform @ Affine.scale(
                dataset.width / width, dataset.height / height
            )
            return BandRead(data=np.asarray(data), transform=transform, crs=str(dataset.crs))
    except RasterioIOError as exc:
        raise BandReadError(f"{band.href}: {exc}") from exc


__all__ = [
    "Band",
    "BandRead",
    "BandReadError",
    "Scene",
    "ScenePage",
    "SceneParseError",
    "parse_scene_page",
    "read_band",
    "search_params",
]
