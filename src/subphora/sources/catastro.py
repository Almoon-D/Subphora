# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Catastro: the requests for one parcel and the parsers of their answers.

Observed behaviour (docs/knowledge/catastro.md):
- The INSPIRE WFS answers a missing or malformed reference with HTTP 200 and an OWS
  ``ExceptionReport``: the body decides, not the status.
- The WFS does not always answer in the CRS asked for (EPSG:4083 requests come back in
  EPSG:4326), so the parser returns the ``srsName`` each geometry declares, and positions
  stay in that CRS's own axis order for ``geo`` to reproject.
- The non-protected data service (``Consulta_DNPRC``) names the municipality and province;
  a parcel with several properties comes back as a list of them, one with a single
  property as one record.
"""

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from subphora.domain.parcels import LookupFailure, ParcelLookupError

WFS_SERVICE_ID = "catastro-wfs-parcels"
OVC_SERVICE_ID = "catastro-ovc"
DNPRC_PATH = "/COVCCallejero.svc/json/Consulta_DNPRC"
# The CRS asked of the WFS. Every location answers in it, the Canaries included (which
# ignore EPSG:4083); the parser still trusts only the srsName of the answer.
REQUESTED_SRS = "EPSG::4326"

_NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "cp": "http://inspire.ec.europa.eu/schemas/cp/4.0",
    "ows": "http://www.opengis.net/ows/1.1",
}
_GML = "{" + _NS["gml"] + "}"
_NOT_FOUND_TEXT = "No se ha encontrado la parcela"
_BAD_REFERENCE_TEXT = "Invalid length of REFCAT"
_EPSG_FORMS = (
    re.compile(r"^https?://www\.opengis\.net/def/crs/EPSG/0/(\d+)$"),
    re.compile(r"^urn:ogc:def:crs:EPSG:[\d.]*:(\d+)$"),
    re.compile(r"^EPSG:{1,2}(\d+)$"),
)
# DNPRC error code for "no property with these parameters".
_DNPRC_NOT_FOUND = "5"

type Pair = tuple[float, float]
type RawRing = tuple[Pair, ...]
type RawPolygon = tuple[RawRing, ...]


@dataclass(frozen=True, slots=True)
class RawParcel:
    """A WFS parcel before reprojection: positions in ``srs``'s own axis order."""

    reference: str
    area_m2: float
    srs: str
    polygons: tuple[RawPolygon, ...]
    reference_point: Pair
    reference_point_srs: str


@dataclass(frozen=True, slots=True)
class ParcelPlace:
    """Where a parcel is, from the non-protected data service."""

    municipality: str
    province: str
    # The two-digit INE province code (``loine.cp``).
    province_code: str


def wfs_parcel_params(parcel: str) -> dict[str, str]:
    return {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "STOREDQUERY_ID": "GetParcel",
        "refcat": parcel,
        "srsname": REQUESTED_SRS,
    }


def dnprc_params(parcel: str) -> dict[str, str]:
    return {"RefCat": parcel}


def _upstream(detail: str) -> ParcelLookupError:
    return ParcelLookupError(LookupFailure.UPSTREAM_ERROR, f"Catastro: {detail}")


def epsg_of(srs_name: str) -> str:
    """``EPSG:<code>`` from the forms GML uses for a CRS identifier."""
    for form in _EPSG_FORMS:
        match = form.match(srs_name.strip())
        if match:
            return f"EPSG:{match.group(1)}"
    raise _upstream(f"unrecognised srsName {srs_name!r}")


def parse_wfs_parcel(content: bytes, parcel: str) -> RawParcel:
    """The parcel in a GetParcel answer; raises ParcelLookupError for every other answer."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise _upstream(f"the parcel service answered with malformed XML ({exc})") from exc
    if root.tag == "{" + _NS["ows"] + "}ExceptionReport":
        raise _exception_report(root)
    if root.tag != "{" + _NS["wfs"] + "}FeatureCollection":
        raise _upstream(f"unexpected answer from the parcel service: {root.tag}")
    members = root.findall("wfs:member/cp:CadastralParcel", _NS)
    matching = [m for m in members if _text(m, "cp:nationalCadastralReference") == parcel]
    if not matching:
        raise ParcelLookupError(
            LookupFailure.NOT_FOUND, f"Catastro has no parcel with reference {parcel}"
        )
    return _parcel(matching[0], parcel)


def _exception_report(root: ET.Element) -> ParcelLookupError:
    text = " ".join(
        (element.text or "").strip() for element in root.iterfind(".//ows:ExceptionText", _NS)
    )
    if _NOT_FOUND_TEXT in text:
        return ParcelLookupError(LookupFailure.NOT_FOUND, f"Catastro: {text}")
    if _BAD_REFERENCE_TEXT in text:
        return ParcelLookupError(LookupFailure.MALFORMED, f"Catastro: {text}")
    return _upstream(f"the parcel service reported an error: {text or 'no text'}")


def _text(element: ET.Element, path: str) -> str | None:
    found = element.find(path, _NS)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _parcel(element: ET.Element, parcel: str) -> RawParcel:
    area_text = _text(element, "cp:areaValue")
    try:
        area = float(area_text) if area_text is not None else 0.0
    except ValueError:
        area = 0.0
    if area <= 0:
        raise _upstream("the parcel has no valid areaValue")
    geometry = element.find("cp:geometry/gml:MultiSurface", _NS)
    if geometry is None:
        raise _upstream("the parcel has no MultiSurface geometry")
    srs = _srs(geometry, None)
    if srs is None:
        raise _upstream("the parcel declares no srsName")
    polygons = tuple(_polygons(geometry, srs))
    if not polygons:
        raise _upstream("the parcel has no polygon")
    point = element.find("cp:referencePoint/gml:Point", _NS)
    position = None if point is None else point.find("gml:pos", _NS)
    if point is None or position is None or not position.text:
        raise _upstream("the parcel has no reference point")
    point_srs = _srs(point, srs) or srs
    pairs = _pairs(position.text, "the reference point")
    if len(pairs) != 1:
        raise _upstream("the parcel has a malformed reference point")
    return RawParcel(
        reference=parcel,
        area_m2=area,
        srs=srs,
        polygons=polygons,
        reference_point=pairs[0],
        reference_point_srs=point_srs,
    )


def _srs(element: ET.Element, inherited: str | None) -> str | None:
    name = element.get("srsName")
    return epsg_of(name) if name else inherited


def _polygons(geometry: ET.Element, srs: str) -> Iterator[RawPolygon]:
    """Every polygon of a MultiSurface: Surface patches or plain Polygons."""
    for member in geometry.iterfind("gml:surfaceMember", _NS):
        for surface in member:
            surface_srs = _srs(surface, srs)
            if surface_srs != srs:
                raise _upstream(f"a surface in {surface_srs} inside a MultiSurface in {srs}")
            patches = (
                surface.findall("gml:patches/gml:PolygonPatch", _NS)
                if surface.tag == _GML + "Surface"
                else [surface]
            )
            for patch in patches:
                yield _polygon(patch)


def _polygon(patch: ET.Element) -> RawPolygon:
    exterior = patch.find("gml:exterior/gml:LinearRing/gml:posList", _NS)
    if exterior is None or not exterior.text:
        raise _upstream("a polygon without an exterior ring")
    rings = [_ring(exterior)]
    for interior in patch.iterfind("gml:interior/gml:LinearRing/gml:posList", _NS):
        rings.append(_ring(interior))
    return tuple(rings)


def _ring(pos_list: ET.Element) -> RawRing:
    dimension = pos_list.get("srsDimension", "2")
    if dimension != "2":
        raise _upstream(f"a ring with srsDimension {dimension}")
    pairs = _pairs(pos_list.text or "", "ring")
    # A closed linear ring has at least four positions, the last equal to the first.
    if len(pairs) < 4 or pairs[0] != pairs[-1]:
        raise _upstream("a ring that is not closed")
    return pairs


def _pairs(text: str, what: str) -> tuple[Pair, ...]:
    try:
        numbers = [float(value) for value in text.split()]
    except ValueError as exc:
        raise _upstream(f"non-numeric coordinates in {what}") from exc
    if not numbers or len(numbers) % 2:
        raise _upstream(f"an odd number of coordinates in {what}")
    return tuple(zip(numbers[0::2], numbers[1::2], strict=True))


def parse_dnprc(content: bytes, parcel: str) -> ParcelPlace:
    """Municipality and province from a ``Consulta_DNPRC`` answer."""
    try:
        result = json.loads(content)["consulta_dnprcResult"]
    except (ValueError, KeyError, TypeError) as exc:
        raise _upstream("the cadastral data service answered with malformed JSON") from exc
    if not isinstance(result, dict):
        raise _upstream("the cadastral data service answered with an unexpected document")
    errors = result.get("lerr")
    if errors:
        codes = {str(error.get("cod")) for error in errors if isinstance(error, dict)}
        if _DNPRC_NOT_FOUND in codes:
            raise ParcelLookupError(
                LookupFailure.NOT_FOUND, f"Catastro has no property data for {parcel}"
            )
        raise _upstream(f"the cadastral data service reported errors {sorted(codes)}")
    location = _dnprc_location(result)
    try:
        municipality = str(location["nm"]).strip()
        province = str(location["np"]).strip()
        province_code = str(location["loine"]["cp"]).strip().zfill(2)
    except (KeyError, TypeError) as exc:
        raise _upstream("no municipality or province in the answer") from exc
    if not municipality or not province:
        raise _upstream("an empty municipality or province in the answer")
    return ParcelPlace(municipality=municipality, province=province, province_code=province_code)


def _dnprc_location(result: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        if "bico" in result:
            location = result["bico"]["bi"]["dt"]
        else:
            # Several properties: they share the parcel, so the first one's place is the
            # parcel's.
            location = result["lrcdnp"]["rcdnp"][0]["dt"]
    except (KeyError, IndexError, TypeError) as exc:
        raise _upstream("the cadastral data service answered without a location") from exc
    if not isinstance(location, Mapping):
        raise _upstream("the cadastral data service answered without a location")
    return location
