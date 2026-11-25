# Copyright (c) 2026 Almoon-D. All rights reserved.
"""SIGPAC's query service: the enclosures of a reference, and the enclosure under a point.

Observed behaviour (docs/knowledge/sigpac.md):
- ``recinfo`` (one enclosure) and ``recinfoparc`` (every enclosure of a parcel) answer
  GeoJSON with one feature per enclosure, in EPSG:4258, longitude first, the CRS named in a
  ``crs`` member; nothing found is HTTP 200 with no feature and an empty ``crs``.
- ``recinfobypoint`` answers a JSON list of the enclosures at a point (with a WKT outline
  we do not need), or an empty list where SIGPAC has none: at sea, outside Spain, and in
  Ceuta and Melilla, which it does not cover.
- Areas (``superficie``) are hectares; province codes are numbers (34, not "34").
"""

import json
from dataclasses import dataclass
from typing import Any

from subphora.domain.aoi import SearchError, SearchFailure

SERVICE_ID = "sigpac-queries"
# ETRS89 geographic: what every answer is in, and what a point is asked in.
SIGPAC_CRS = "EPSG:4258"
_CRS_CODE = "4258"
# Decimals of a point in the path: 0.000001° is about 0.1 m, and equal points share a cache.
_POINT_DECIMALS = 6
_HECTARE_M2 = 10_000.0
# province:municipality:aggregate:zone:polygon:parcel:enclosure.
_ENCLOSURE_PARTS = 7
_MIN_RING_POSITIONS = 4

type Pair = tuple[float, float]
type RawRing = tuple[Pair, ...]
type RawPolygon = tuple[RawRing, ...]


@dataclass(frozen=True, slots=True)
class Enclosure:
    """One enclosure: positions (longitude, latitude) in EPSG:4258."""

    province: int
    number: int
    area_m2: float
    polygons: tuple[RawPolygon, ...]


def _upstream(detail: str) -> SearchError:
    return SearchError(SearchFailure.UPSTREAM_ERROR, f"SIGPAC: {detail}", SERVICE_ID)


def reference_path(parts: tuple[int, ...]) -> str:
    """The path of an enclosure (seven parts) or of a whole parcel (six)."""
    route = "recinfo" if len(parts) == _ENCLOSURE_PARTS else "recinfoparc"
    return f"/query/{route}/{'/'.join(str(part) for part in parts)}.geojson"


def point_path(lon: float, lat: float) -> str:
    digits = _POINT_DECIMALS
    return f"/query/recinfobypoint/{_CRS_CODE}/{lon:.{digits}f}/{lat:.{digits}f}.json"


def _load(content: bytes) -> Any:
    try:
        return json.loads(content)
    except ValueError as exc:
        raise _upstream("the query service answered with malformed JSON") from exc


def parse_enclosures(content: bytes, code: str) -> tuple[Enclosure, ...]:
    """The enclosures of a ``recinfo`` or ``recinfoparc`` answer; raises SearchError."""
    body = _load(content)
    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(features, list):
        raise _upstream("the query service answered without a feature list")
    if not features:
        raise SearchError(
            SearchFailure.NOT_FOUND, f"SIGPAC has no enclosure with reference {code}", SERVICE_ID
        )
    crs = body.get("crs")
    declared = crs.get("properties", {}).get("code") if isinstance(crs, dict) else None
    if str(declared) != _CRS_CODE:
        raise _upstream(f"an answer in CRS {declared!r}, not {_CRS_CODE}")
    return tuple(_enclosure(feature) for feature in features)


def _enclosure(feature: object) -> Enclosure:
    if not isinstance(feature, dict):
        raise _upstream("a feature that is not an object")
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        raise _upstream("a feature without properties or geometry")
    try:
        province = int(properties["provincia"])
        number = int(properties["recinto"])
        area_m2 = float(properties["superficie"]) * _HECTARE_M2
    except (KeyError, TypeError, ValueError) as exc:
        raise _upstream("an enclosure without province, number or area") from exc
    if area_m2 <= 0:
        raise _upstream(f"enclosure {number} has no area")
    return Enclosure(province, number, area_m2, _polygons(geometry))


def _polygons(geometry: dict[str, Any]) -> tuple[RawPolygon, ...]:
    kind, coordinates = geometry.get("type"), geometry.get("coordinates")
    polygons: list[Any]
    match kind:
        case "Polygon":
            polygons = [coordinates]
        case "MultiPolygon":
            polygons = coordinates if isinstance(coordinates, list) else []
        case _:
            raise _upstream(f"an enclosure whose geometry is a {kind}")
    if not polygons or not all(isinstance(p, list) and p for p in polygons):
        raise _upstream("an enclosure without rings")
    return tuple(tuple(_ring(ring) for ring in polygon) for polygon in polygons)


def _ring(ring: object) -> RawRing:
    if not isinstance(ring, list):
        raise _upstream("a ring that is not a list")
    try:
        pairs = tuple((float(p[0]), float(p[1])) for p in ring)
    except (IndexError, TypeError, ValueError) as exc:
        raise _upstream("a ring with non-numeric positions") from exc
    if len(pairs) < _MIN_RING_POSITIONS or pairs[0] != pairs[-1]:
        raise _upstream("a ring that is not closed")
    return pairs


def parse_point(content: bytes) -> int | None:
    """The province of the enclosure at the point, or None where SIGPAC has none."""
    body = _load(content)
    if not isinstance(body, list):
        raise _upstream("the point query answered without a list")
    if not body:
        return None
    first = body[0]
    try:
        return int(first["provincia"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _upstream("an enclosure at the point without a province") from exc
