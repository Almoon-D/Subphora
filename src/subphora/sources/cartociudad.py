# Copyright (c) 2026 Almoon-D. All rights reserved.
"""CartoCiudad's geocoder: candidates for a text, then the one chosen.

Observed behaviour (docs/knowledge/ign-cnig.md):
- ``candidates?q=&limit=`` answers a JSON list; each has an ``id``, a ``type``
  (``Municipio``, ``poblacion``, ``callejero``, ``portal``, ``Codpost``…), an ``address``,
  ``muni``, ``province`` and ``provinceCode``. Most give ``lat`` and ``lng`` as 0.0: only
  ``find`` places them. Nothing found: an empty list.
- ``find?id=&type=`` answers one object with a WKT ``geom``: the boundary of a municipality
  or town (MULTIPOLYGON), a street's line (MULTILINESTRING) or a doorway (POINT); ``lat``
  and ``lng`` are its centre. The id must be passed exactly as the candidate gave it (the
  municipality of Badajoz is "6015"; "06015" answers HTTP 500). An unknown id: HTTP 204.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from subphora.domain.aoi import SearchError, SearchFailure

SERVICE_ID = "cartociudad"
CANDIDATES_PATH = "/candidates"
FIND_PATH = "/find"
# A HTTP status that means "no such place", not a failure.
NO_CONTENT = 204

type Pair = tuple[float, float]
type RawRing = tuple[Pair, ...]
type RawPolygon = tuple[RawRing, ...]

_WKT_HEAD = re.compile(r"^\s*([A-Z]+)\s*(.*)$", re.DOTALL)
_MIN_RING_POSITIONS = 4
# A WKT position here is "x y": longitude and latitude.
_POSITION = 2


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    type: str
    address: str
    municipality: str | None
    province: str | None


@dataclass(frozen=True, slots=True)
class Place:
    """A chosen candidate: its outline when it has one, and its centre."""

    id: str
    type: str
    label: str
    municipality: str | None
    # The two-digit INE province code.
    province_code: str
    # Longitude, latitude in EPSG:4326; None for a place given as a point or a line.
    polygons: tuple[RawPolygon, ...] | None
    centre: Pair


def _upstream(detail: str) -> SearchError:
    return SearchError(SearchFailure.UPSTREAM_ERROR, f"CartoCiudad: {detail}", SERVICE_ID)


def candidates_params(text: str, limit: int) -> dict[str, str]:
    return {"q": text, "limit": str(limit)}


def find_params(place_id: str, place_type: str) -> dict[str, str]:
    return {"id": place_id, "type": place_type}


def _load(content: bytes) -> Any:
    try:
        return json.loads(content)
    except ValueError as exc:
        raise _upstream("the geocoder answered with malformed JSON") from exc


def _text(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_candidates(content: bytes) -> tuple[Candidate, ...]:
    body = _load(content)
    if not isinstance(body, list):
        raise _upstream("the candidates are not a list")
    candidates: list[Candidate] = []
    for record in body:
        if not isinstance(record, dict):
            raise _upstream("a candidate that is not an object")
        place_id, place_type, address = (_text(record, k) for k in ("id", "type", "address"))
        if place_id is None or place_type is None or address is None:
            raise _upstream("a candidate without id, type or address")
        candidates.append(
            Candidate(
                id=place_id,
                type=place_type,
                address=address,
                municipality=_text(record, "muni"),
                province=_text(record, "province"),
            )
        )
    return tuple(candidates)


def parse_find(content: bytes, place_id: str) -> Place:
    """The place of a ``find`` answer; an empty body (HTTP 204) is NOT_FOUND."""
    if not content.strip():
        raise SearchError(
            SearchFailure.NOT_FOUND, f"CartoCiudad has no place {place_id}", SERVICE_ID
        )
    record = _load(content)
    if not isinstance(record, dict):
        raise _upstream("the place is not an object")
    place_type = _text(record, "type")
    province_code = _text(record, "provinceCode")
    if place_type is None or province_code is None:
        raise _upstream("a place without type or province")
    try:
        centre = (float(record["lng"]), float(record["lat"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise _upstream("a place without a centre") from exc
    geometry = _text(record, "geom")
    polygons = _wkt_polygons(geometry) if geometry else None
    if centre == (0.0, 0.0):
        raise _upstream("a place without a centre")
    return Place(
        id=place_id,
        type=place_type,
        label=_label(record, place_type),
        municipality=_text(record, "muni"),
        province_code=province_code.zfill(2),
        polygons=polygons,
        centre=centre,
    )


def _label(record: dict[str, Any], place_type: str) -> str:
    """How the place reads: "CALLE MAYOR 1, Zaragoza", "Daimiel (Ciudad Real)"."""
    municipality = _text(record, "muni")
    province = _text(record, "province")
    town = _text(record, "poblacion") or municipality
    address = _text(record, "address") or town or ""
    if place_type in ("callejero", "portal"):
        street = " ".join(
            part
            for part in (_text(record, "tip_via"), address, _text(record, "portalNumber"))
            if part
        )
        return f"{street}, {town}" if town else street
    if place_type == "poblacion" and municipality and municipality != address:
        return f"{address}, {municipality} ({province})" if province else address
    return f"{address} ({province})" if province else address


def _wkt_polygons(wkt: str) -> tuple[RawPolygon, ...] | None:
    """The polygons of a POLYGON or MULTIPOLYGON; None for any other geometry."""
    match = _WKT_HEAD.match(wkt.upper())
    if match is None:
        raise _upstream("a geometry that is not WKT")
    kind, body = match.groups()
    if kind not in ("POLYGON", "MULTIPOLYGON"):
        return None
    try:
        nested = _nested(body.strip())
    except ValueError as exc:
        raise _upstream(f"a malformed {kind}: {exc}") from exc
    polygons = [nested] if kind == "POLYGON" else nested
    try:
        return tuple(tuple(_ring(ring) for ring in polygon) for polygon in polygons)
    except (TypeError, ValueError) as exc:
        raise _upstream(f"a malformed {kind}") from exc


def _nested(text: str) -> list[Any]:
    """Parenthesised WKT as nested lists, the innermost "x y, x y" as lists of pairs."""
    stack: list[list[Any]] = []
    result: list[Any] | None = None
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            stack.append([])
            start = index + 1
        elif char == ")":
            if not stack:
                raise ValueError("unbalanced parentheses")
            current = stack.pop()
            if not current:  # innermost: the positions
                current = [
                    tuple(float(v) for v in pair.split()) for pair in text[start:index].split(",")
                ]
            if stack:
                stack[-1].append(current)
            else:
                result = current
    if stack or result is None:
        raise ValueError("unbalanced parentheses")
    return result


def _ring(ring: list[tuple[float, ...]]) -> RawRing:
    if any(len(position) != _POSITION for position in ring):
        raise ValueError("a position that is not x y")
    pairs = tuple((position[0], position[1]) for position in ring)
    if len(pairs) < _MIN_RING_POSITIONS or pairs[0] != pairs[-1]:
        raise ValueError("a ring that is not closed")
    return pairs
