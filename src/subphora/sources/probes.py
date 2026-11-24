# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Probes: re-check, live, what the source catalogue records about each service.

Per service, up to four checks: the capabilities document parses and offers every layer of
interest; EPSG:3857 is offered exactly as recorded; CORS is as recorded; one small sample
request answers with the expected content. A service that needs a key is not checked.
"""

import asyncio
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from subphora.config.sources import KINDS_WITH_CAPABILITIES, Service, ServiceKind
from subphora.sources.client import CatalogueClient, FetchedResponse, Params, SourceError
from subphora.sources.models import CheckName, CheckResult, CheckStatus

WEB_MERCATOR = "EPSG:3857"
# A WMTS tile matrix set with this identifier is Web Mercator by definition (OGC 07-057r7).
_WEB_MERCATOR_MATRIX_SETS = frozenset({"GoogleMapsCompatible", "EPSG:3857"})

_CAPABILITIES_PARAMS: dict[ServiceKind, dict[str, str]] = {
    "wms": {"SERVICE": "WMS", "REQUEST": "GetCapabilities", "VERSION": "1.3.0"},
    "wmts": {"SERVICE": "WMTS", "REQUEST": "GetCapabilities"},
    "wfs": {"SERVICE": "WFS", "REQUEST": "GetCapabilities"},
    "wcs": {"SERVICE": "WCS", "REQUEST": "GetCapabilities", "VERSION": "2.0.1"},
    "ogc_api": {"f": "json"},
}
_WFS_CRS_TAGS = ("DefaultCRS", "OtherCRS", "DefaultSRS", "OtherSRS", "SRS")
_EXCEPTION_ROOTS = frozenset({"ServiceExceptionReport", "ExceptionReport"})


class CapabilitiesError(ValueError):
    """A capabilities document that cannot be read as the service kind's."""


@dataclass(frozen=True, slots=True)
class Capabilities:
    layers: frozenset[str]
    crs: frozenset[str]

    @property
    def web_mercator(self) -> bool:
        return WEB_MERCATOR in self.crs or bool(self.crs & _WEB_MERCATOR_MATRIX_SETS)


def normalise_crs(value: str) -> str:
    """``urn:ogc:def:crs:EPSG::3857`` and ``…/def/crs/EPSG/0/3857`` → ``EPSG:3857``."""
    text = value.strip()
    lowered = text.lower()
    if lowered.startswith("urn:ogc:def:crs:epsg:"):
        return "EPSG:" + text.rsplit(":", 1)[-1]
    if "/def/crs/epsg/" in lowered:
        return "EPSG:" + text.rstrip("/").rsplit("/", 1)[-1]
    if lowered.startswith("epsg:"):
        return "EPSG:" + text[5:]
    return text


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texts(root: ET.Element, *names: str) -> list[str]:
    wanted = set(names)
    return [
        element.text.strip()
        for element in root.iter()
        if _local(element.tag) in wanted and element.text and element.text.strip()
    ]


def _children_texts(root: ET.Element, parent: str, child: str) -> list[str]:
    """Text of each ``child`` directly under each ``parent`` (any namespace)."""
    found = []
    for element in root.iter():
        if _local(element.tag) != parent:
            continue
        for sub in element:
            if _local(sub.tag) == child and sub.text and sub.text.strip():
                found.append(sub.text.strip())
    return found


def parse_capabilities(
    kind: ServiceKind, content: bytes, of_interest: frozenset[str] = frozenset()
) -> Capabilities:
    """Layers and CRS of a capabilities document; raises CapabilitiesError.

    A WFS lists CRS per feature type: only those of the feature types of interest count
    (all of them when none is named).
    """
    if kind == "ogc_api":
        return _parse_ogc_api(content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise CapabilitiesError(f"not XML: {exc}") from exc
    name = _local(root.tag)
    if name in _EXCEPTION_ROOTS:
        message = " ".join(_texts(root, "ServiceException", "ExceptionText"))
        raise CapabilitiesError(f"the service answered an exception: {message[:200]}")
    if kind == "wms" and name in {"WMS_Capabilities", "WMT_MS_Capabilities"}:
        crs = [code for text in _texts(root, "CRS", "SRS") for code in text.split()]
        return _capabilities(_children_texts(root, "Layer", "Name"), crs)
    if kind == "wmts" and name == "Capabilities":
        layers = _children_texts(root, "Layer", "Identifier")
        crs = _texts(root, "SupportedCRS") + _children_texts(root, "TileMatrixSet", "Identifier")
        return _capabilities(layers, crs)
    if kind == "wfs" and name == "WFS_Capabilities":
        crs = []
        for feature_type in (e for e in root.iter() if _local(e.tag) == "FeatureType"):
            names = _children_texts(feature_type, "FeatureType", "Name")
            if not of_interest or of_interest.intersection(names):
                crs += _texts(feature_type, *_WFS_CRS_TAGS)
        return _capabilities(_children_texts(root, "FeatureType", "Name"), crs)
    if kind == "wcs" and name in {"Capabilities", "WCS_Capabilities"}:
        layers = _texts(root, "CoverageId") or _children_texts(
            root, "CoverageOfferingBrief", "name"
        )
        return _capabilities(layers, [])
    raise CapabilitiesError(f"root element {name!r} is not a {kind} capabilities document")


def _parse_ogc_api(content: bytes) -> Capabilities:
    try:
        document = json.loads(content)
    except ValueError as exc:
        raise CapabilitiesError(f"not JSON: {exc}") from exc
    collections = document.get("collections") if isinstance(document, dict) else None
    if not isinstance(collections, list):
        raise CapabilitiesError("no 'collections' list in the OGC API response")
    ids = [c["id"] for c in collections if isinstance(c, dict) and isinstance(c.get("id"), str)]
    return _capabilities(ids, [])


def _capabilities(layers: list[str], crs: list[str]) -> Capabilities:
    if not layers:
        raise CapabilitiesError("the document lists no layers")
    return Capabilities(frozenset(layers), frozenset(normalise_crs(code) for code in crs))


def capabilities_request(service: Service) -> tuple[str, Params]:
    url = service.base_url
    if service.kind == "ogc_api":
        url = url.rstrip("/") + "/collections"
    return url, _CAPABILITIES_PARAMS[service.kind]


def _result(service: Service, check: CheckName, status: CheckStatus, detail: str) -> CheckResult:
    return CheckResult(service_id=service.id, check=check, status=status, detail=detail)


def _cors_allowed(response: FetchedResponse, origin: str) -> bool:
    allowed = response.headers.get("access-control-allow-origin", "").strip()
    return allowed in {"*", origin}


async def check_service(
    client: CatalogueClient, service: Service, origin: str
) -> list[CheckResult]:
    """Every applicable check of one service."""
    if service.needs_key:
        return [
            _result(
                service,
                CheckName.SAMPLE,
                CheckStatus.NOT_CHECKED,
                f"needs a key ({service.key_env}); probed by the session that uses the key",
            )
        ]
    results: list[CheckResult] = []
    reached = False
    capabilities: Capabilities | None = None

    # Capabilities and sample go without an Origin, as the server will call them; some
    # firewalls reject any request that carries one (docs/knowledge/water-authorities.md).
    if service.kind in KINDS_WITH_CAPABILITIES:
        result, capabilities, response = await _check_capabilities(client, service)
        results.append(result)
        reached = reached or response is not None
        if service.web_mercator is not None:
            results.append(_check_web_mercator(service, capabilities))

    if service.sample is not None:
        result, response = await _check_sample(client, service)
        results.append(result)
        reached = reached or response is not None

    if service.cors is not None:
        results.append(await _check_cors(client, service, origin, reached))
    return results


def _sample_request(service: Service) -> tuple[str, Params]:
    sample = service.sample
    assert sample is not None
    url = service.base_url.rstrip("/") + sample.path if sample.path else service.base_url
    return url, sample.params


async def _check_capabilities(
    client: CatalogueClient, service: Service
) -> tuple[CheckResult, Capabilities | None, FetchedResponse | None]:
    url, params = capabilities_request(service)
    try:
        response = await client.get(url, params=params)
    except SourceError as exc:
        return _result(service, CheckName.CAPABILITIES, CheckStatus.FAILED, str(exc)), None, None
    if response.status_code != 200:
        detail = f"HTTP {response.status_code}"
        return _result(service, CheckName.CAPABILITIES, CheckStatus.FAILED, detail), None, response
    try:
        capabilities = parse_capabilities(service.kind, response.content, frozenset(service.layers))
    except CapabilitiesError as exc:
        failed = _result(service, CheckName.CAPABILITIES, CheckStatus.FAILED, str(exc))
        return failed, None, response
    missing = sorted(set(service.layers) - capabilities.layers)
    if missing:
        detail = f"layers missing: {', '.join(missing)}"
        return _result(service, CheckName.CAPABILITIES, CheckStatus.FAILED, detail), None, response
    detail = (
        f"{len(capabilities.layers)} layers offered; all {len(service.layers)} of interest present"
    )
    return _result(service, CheckName.CAPABILITIES, CheckStatus.OK, detail), capabilities, response


def _check_web_mercator(service: Service, capabilities: Capabilities | None) -> CheckResult:
    if capabilities is None:
        return _result(
            service, CheckName.WEB_MERCATOR, CheckStatus.NOT_CHECKED, "capabilities unavailable"
        )
    offered = capabilities.web_mercator
    if offered == service.web_mercator:
        detail = "offered" if offered else "not offered, as recorded: needs the server's proxy"
        return _result(service, CheckName.WEB_MERCATOR, CheckStatus.OK, detail)
    detail = (
        f"catalogue says {'offered' if service.web_mercator else 'not offered'}, "
        f"the service says {'offered' if offered else 'not offered'}"
    )
    return _result(service, CheckName.WEB_MERCATOR, CheckStatus.FAILED, detail)


async def _check_sample(
    client: CatalogueClient, service: Service
) -> tuple[CheckResult, FetchedResponse | None]:
    sample = service.sample
    assert sample is not None
    url, params = _sample_request(service)
    try:
        response = await client.get(url, params=params)
    except SourceError as exc:
        return _result(service, CheckName.SAMPLE, CheckStatus.FAILED, str(exc)), None
    if response.status_code != 200:
        detail = f"HTTP {response.status_code}"
        return _result(service, CheckName.SAMPLE, CheckStatus.FAILED, detail), response
    content_type = response.content_type.split(";")[0].strip().lower()
    if not content_type.startswith(sample.expect_content_type.lower()):
        detail = (
            f"expected {sample.expect_content_type}, got {content_type or 'no content type'}: "
            f"{_snippet(response)}"
        )
        return _result(service, CheckName.SAMPLE, CheckStatus.FAILED, detail), response
    if sample.expect_text is not None and sample.expect_text not in response.text:
        detail = f"the response lacks {sample.expect_text!r}: {_snippet(response)}"
        return _result(service, CheckName.SAMPLE, CheckStatus.FAILED, detail), response
    detail = f"{sample.description} ({len(response.content)} bytes)"
    return _result(service, CheckName.SAMPLE, CheckStatus.OK, detail), response


def _snippet(response: FetchedResponse) -> str:
    return " ".join(response.text[:120].split())


async def _check_cors(
    client: CatalogueClient, service: Service, origin: str, reached: bool
) -> CheckResult:
    """Repeat the sample (or capabilities) request as a browser would, with an Origin."""
    if not reached:
        return _result(service, CheckName.CORS, CheckStatus.NOT_CHECKED, "service unreachable")
    url, params = (
        _sample_request(service) if service.sample is not None else capabilities_request(service)
    )
    try:
        response = await client.get(url, params=params, headers={"Origin": origin})
    except SourceError as exc:
        return _result(service, CheckName.CORS, CheckStatus.NOT_CHECKED, str(exc))
    allowed = _cors_allowed(response, origin)
    if allowed == service.cors:
        detail = "allowed" if allowed else "not allowed, as recorded: needs the server's proxy"
        return _result(service, CheckName.CORS, CheckStatus.OK, detail)
    detail = (
        f"catalogue says {'allowed' if service.cors else 'not allowed'}, "
        f"the service says {'allowed' if allowed else 'not allowed'}"
    )
    return _result(service, CheckName.CORS, CheckStatus.FAILED, detail)


async def check_catalogue(
    client: CatalogueClient, services: list[Service], origin: str
) -> list[CheckResult]:
    """All services at once; the client's per-host limits keep it polite."""
    per_service = await asyncio.gather(
        *(check_service(client, service, origin) for service in services)
    )
    return [result for results in per_service for result in results]


def format_table(results: list[CheckResult]) -> str:
    """One row per service and check, aligned for a terminal."""
    header = ("SERVICE", "CHECK", "STATUS", "DETAIL")
    rows = [(r.service_id, r.check.value, r.status.value, r.detail) for r in results]
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(3)]
    lines = [
        "  ".join(cell.ljust(width) for cell, width in zip(row[:3], widths, strict=True))
        + "  "
        + row[3]
        for row in [header, *rows]
    ]
    counts = {status: sum(r.status is status for r in results) for status in CheckStatus}
    summary = ", ".join(f"{count} {status.value}" for status, count in counts.items())
    return "\n".join([*lines, "", summary])
