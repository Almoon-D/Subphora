# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Requests and answers of the nationwide inputs (docs/knowledge/nationwide-inputs.md).

Observed behaviour:
- IGME's ArcGIS REST ``query`` takes an envelope in any EPSG code (``inSR``), answers
  GeoJSON in ``outSR`` with x (easting) first, drops vertices closer than
  ``maxAllowableOffset`` (in ``outSR`` units), pages with ``resultOffset`` and
  ``resultRecordCount`` (at most 1,000), and says ``exceededTransferLimit`` while more
  pages follow. An error comes as HTTP 200 with an ``error`` object; "Failed to execute
  query" came now and then under concurrent queries, and the same page answered later.
- The IGN MDT WCS 2.0.1 answers a GeoTIFF of integer metres for a ``subset`` window in the
  coverage's CRS, 0 at sea, and an ``ExtentError`` exception report (HTTP 400) for a
  window outside the coverage.
- SoilGrids' WCS 2.0.1 answers a GeoTIFF in EPSG:4326 for ``long``/``lat`` subsets.
- MITECO's GeoServer WFS 2.0 answers GeoJSON in a listed ``srsName`` (EPSG:3857: x first),
  pages with ``startIndex`` and ``count`` once sorted, and states ``numberMatched``.
"""

import json
from dataclasses import dataclass
from typing import Any

type Bounds = tuple[float, float, float, float]
type Feature = dict[str, Any]


class InputParseError(ValueError):
    """An answer that is not the data asked for; ``transient`` when the service reported a
    failure of its own that the same request may not meet again."""

    def __init__(self, detail: str, *, transient: bool = False) -> None:
        super().__init__(detail)
        self.transient = transient


def _epsg_number(crs: str) -> str:
    prefix, _, number = crs.partition(":")
    if prefix != "EPSG" or not number.isdigit():
        raise ValueError(f"{crs!r} is not an EPSG code")
    return number


def arcgis_query_params(
    bounds: Bounds,
    crs: str,
    fields: list[str],
    offset: int,
    count: int,
    generalise: float | None = None,
) -> dict[str, str]:
    """One page of the features intersecting ``bounds`` (in ``crs``), answered in ``crs``."""
    number = _epsg_number(crs)
    params = {
        "geometry": ",".join(f"{value:.1f}" for value in bounds),
        "geometryType": "esriGeometryEnvelope",
        "inSR": number,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(fields),
        "outSR": number,
        "returnGeometry": "true",
        "orderByFields": "OBJECTID",
        "resultOffset": str(offset),
        "resultRecordCount": str(count),
        "f": "geojson",
    }
    if generalise:
        params["maxAllowableOffset"] = f"{generalise:g}"
    return params


@dataclass(frozen=True, slots=True)
class Page:
    features: list[Feature]
    more: bool


def _json(content: bytes) -> Any:
    if content.lstrip().startswith(b"<"):
        raise InputParseError("the service answered XML, not JSON")
    try:
        return json.loads(content)
    except ValueError as exc:
        raise InputParseError(f"not JSON: {exc}") from exc


def parse_arcgis_page(content: bytes) -> Page:
    body = _json(content)
    if not isinstance(body, dict):
        raise InputParseError("not a JSON object")
    if "error" in body:
        error = body["error"]
        message = error.get("message", error) if isinstance(error, dict) else error
        # Under concurrent queries IGME answered "Failed to execute query" for a page that
        # answered on its own (docs/knowledge/nationwide-inputs.md).
        raise InputParseError(f"the service refused the query: {message}", transient=True)
    features = body.get("features")
    if not isinstance(features, list):
        raise InputParseError("not a GeoJSON FeatureCollection")
    more = bool(body.get("exceededTransferLimit")) or bool(
        (body.get("properties") or {}).get("exceededTransferLimit")
    )
    return Page(features=[f for f in features if isinstance(f, dict)], more=more)


def wfs_page_params(
    type_name: str, srs: str, bounds: Bounds, sort_by: str, start: int, count: int
) -> dict[str, str]:
    """One page of the features intersecting ``bounds`` (in ``srs``), answered in ``srs``."""
    box = ",".join(f"{value:.1f}" for value in bounds)
    return {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "application/json",
        "srsName": srs,
        "bbox": f"{box},{srs}",
        "sortBy": sort_by,
        "startIndex": str(start),
        "count": str(count),
    }


def parse_wfs_page(content: bytes, count: int) -> Page:
    body = _json(content)
    if not isinstance(body, dict) or not isinstance(body.get("features"), list):
        raise InputParseError("not a GeoJSON FeatureCollection")
    features = [f for f in body["features"] if isinstance(f, dict)]
    return Page(features=features, more=len(features) == count)


def wcs_params(coverage: str, bounds: Bounds) -> dict[str, str | list[str]]:
    """A GeoTIFF window of an IGN MDT coverage, ``bounds`` in the coverage's CRS."""
    west, south, east, north = bounds
    return {
        "service": "WCS",
        "version": "2.0.1",
        "request": "GetCoverage",
        "CoverageId": coverage,
        "subset": [f"x({west:.1f},{east:.1f})", f"y({south:.1f},{north:.1f})"],
        "format": "image/tiff",
    }


_EPSG_4326_URI = "http://www.opengis.net/def/crs/EPSG/0/4326"


def soilgrids_params(coverage: str, bounds: Bounds) -> dict[str, str | list[str]]:
    """A GeoTIFF window of a SoilGrids coverage, ``bounds`` in degrees."""
    west, south, east, north = bounds
    return {
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": coverage,
        "FORMAT": "image/tiff",
        "SUBSET": [f"long({west:.4f},{east:.4f})", f"lat({south:.4f},{north:.4f})"],
        "SUBSETTINGCRS": _EPSG_4326_URI,
        "OUTPUTCRS": _EPSG_4326_URI,
    }


_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def check_tiff(content: bytes) -> None:
    """Raise InputParseError unless the answer is a TIFF (a WCS error is XML)."""
    if not content.startswith(_TIFF_MAGIC):
        text = content[:300].decode("utf-8", errors="replace")
        raise InputParseError(f"not a GeoTIFF: {' '.join(text.split())[:200]}")


__all__ = [
    "Feature",
    "InputParseError",
    "Page",
    "arcgis_query_params",
    "check_tiff",
    "parse_arcgis_page",
    "parse_wfs_page",
    "soilgrids_params",
    "wcs_params",
    "wfs_page_params",
]
