# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Probes against trimmed real responses (tests/fixtures/sources/README.md)."""

from typing import Any

import httpx
import pytest
import respx

from subphora.config.sources import Service
from subphora.sources import (
    CatalogueClient,
    CheckName,
    CheckResult,
    CheckStatus,
    check_catalogue,
    check_service,
    format_table,
)
from subphora.sources.probes import (
    CapabilitiesError,
    capabilities_request,
    normalise_crs,
    parse_capabilities,
)
from tests.support import ORIGIN, catalogue, fixture_bytes, service

CATASTRO_WMS = "https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx"
CATASTRO_WFS = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
XML = {"content-type": "text/xml; charset=iso-8859-1", "access-control-allow-origin": "*"}
PNG = {"content-type": "image/png", "access-control-allow-origin": "*"}

MAP_SAMPLE: dict[str, Any] = {
    "description": "a map",
    "params": {"REQUEST": "GetMap"},
    "expect_content_type": "image/png",
}


def catastro_wms(**overrides: Any) -> dict[str, Any]:
    entry = service(
        id="catastro-wms",
        base_url=CATASTRO_WMS,
        layers=["CP.CadastralParcel", "CP.CadastralZoning"],
        sample=MAP_SAMPLE,
    )
    entry.update(overrides)
    return entry


def statuses(results: list[CheckResult]) -> dict[CheckName, CheckStatus]:
    return {result.check: result.status for result in results}


def details(results: list[CheckResult]) -> dict[CheckName, str]:
    return {result.check: result.detail for result in results}


async def run(entry: dict[str, Any], mock: respx.MockRouter) -> list[CheckResult]:
    sources = catalogue(entry)
    async with CatalogueClient(sources, "0.1.0") as client:
        return await check_service(client, sources.services[0], ORIGIN)


# ── Parsing ──────────────────────────────────────────────────────────────────────────


def test_a_wms_capabilities_document_lists_layers_and_crs() -> None:
    caps = parse_capabilities("wms", fixture_bytes("catastro_wms_capabilities.xml"))
    assert {"CP.CadastralParcel", "CP.CadastralZoning", "BU.Building"} <= caps.layers
    assert "WMS" not in caps.layers  # the service's own Name is not a layer
    assert caps.web_mercator
    assert {"EPSG:25830", "EPSG:4326"} <= caps.crs


def test_a_wms_without_web_mercator_is_seen() -> None:
    caps = parse_capabilities("wms", fixture_bytes("igme_lithostrat_wms_capabilities.xml"))
    assert {"0", "1", "2"} <= caps.layers
    assert not caps.web_mercator


def test_a_wmts_capabilities_document_lists_layers_and_matrix_sets() -> None:
    caps = parse_capabilities("wmts", fixture_bytes("ign_pnoa_wmts_capabilities.xml"))
    assert caps.layers == {"OI.OrthoimageCoverage"}
    assert "GoogleMapsCompatible" in caps.crs
    assert caps.web_mercator


def test_a_wfs_counts_only_the_crs_of_the_feature_types_of_interest() -> None:
    content = fixture_bytes("miteco_wfs_capabilities.xml")
    status = parse_capabilities("wfs", content, frozenset({"agua:estado_masas_aguasub_2027"}))
    assert status.layers == {"agua:estado_masas_aguasub_2027", "agua:rios_pfaf_cx1"}
    assert status.web_mercator
    assert "EPSG:25830" in status.crs
    everything = parse_capabilities("wfs", content)
    assert status.crs <= everything.crs


def test_a_catastro_wfs_offers_parcels_in_web_mercator() -> None:
    caps = parse_capabilities("wfs", fixture_bytes("catastro_wfs_capabilities.xml"))
    assert caps.layers == {"cp:CadastralParcel", "cp:CadastralZoning"}
    assert caps.web_mercator


def test_a_wcs_capabilities_document_lists_coverages() -> None:
    caps = parse_capabilities("wcs", fixture_bytes("ign_mdt_wcs_capabilities.xml"))
    assert {"Elevacion25830_5", "Elevacion25830_25", "Elevacion4083_5"} <= caps.layers
    assert caps.crs == frozenset()


def test_an_ogc_api_collections_document_lists_collections() -> None:
    caps = parse_capabilities("ogc_api", fixture_bytes("sigpac_ogcapi_collections.json"))
    assert {"recintos", "cultivo_declarado"} <= caps.layers


@pytest.mark.parametrize(
    ("kind", "content", "message"),
    [
        ("wms", fixture_bytes("capabilities_truncated.xml"), "not XML"),
        ("wms", fixture_bytes("catastro_rejected.html"), "not XML"),
        ("wfs", fixture_bytes("catastro_wfs_not_found.xml"), "No se ha encontrado"),
        ("wmts", fixture_bytes("catastro_wms_capabilities.xml"), "not a wmts"),
        ("wms", b"<WMS_Capabilities><Capability/></WMS_Capabilities>", "no layers"),
        ("ogc_api", b"{not json", "not JSON"),
        ("ogc_api", b'{"links": []}', "collections"),
        ("ogc_api", b"[]", "collections"),
    ],
)
def test_malformed_capabilities_are_refused(kind: Any, content: bytes, message: str) -> None:
    with pytest.raises(CapabilitiesError, match=message):
        parse_capabilities(kind, content)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("urn:ogc:def:crs:EPSG::3857", "EPSG:3857"),
        ("http://www.opengis.net/def/crs/EPSG/0/25830", "EPSG:25830"),
        ("epsg:4326", "EPSG:4326"),
        ("CRS:84", "CRS:84"),
    ],
)
def test_crs_codes_are_normalised(code: str, expected: str) -> None:
    assert normalise_crs(code) == expected


def test_an_ogc_api_is_asked_for_its_collections() -> None:
    entry = Service.model_validate(
        service(kind="ogc_api", base_url="https://api.example.org/ogcapi/", web_mercator=None)
    )
    assert capabilities_request(entry) == (
        "https://api.example.org/ogcapi/collections",
        {"f": "json"},
    )


# ── Checks of one service ────────────────────────────────────────────────────────────


async def test_a_healthy_service_passes_every_check() -> None:
    with respx.mock as mock:
        mock.get(CATASTRO_WMS, params={"REQUEST": "GetCapabilities"}).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        mock.get(CATASTRO_WMS, params={"REQUEST": "GetMap"}).respond(
            200, content=fixture_bytes("catastro_wms_map.png"), headers=PNG
        )
        results = await run(catastro_wms(), mock)
    assert statuses(results) == {
        CheckName.CAPABILITIES: CheckStatus.OK,
        CheckName.WEB_MERCATOR: CheckStatus.OK,
        CheckName.SAMPLE: CheckStatus.OK,
        CheckName.CORS: CheckStatus.OK,
    }
    assert "all 2 of interest present" in details(results)[CheckName.CAPABILITIES]


async def test_the_probe_sends_the_origin_and_the_user_agent() -> None:
    with respx.mock as mock:
        route = mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        await run(catastro_wms(sample=None), mock)
    request = route.calls.last.request
    assert request.headers["Origin"] == ORIGIN
    assert request.headers["User-Agent"] == "subphora/0.1.0"


async def test_a_missing_layer_fails_the_capabilities_check() -> None:
    entry = catastro_wms(layers=["CP.CadastralParcel", "Not.There"], sample=None)
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        results = await run(entry, mock)
    assert statuses(results)[CheckName.CAPABILITIES] is CheckStatus.FAILED
    assert details(results)[CheckName.CAPABILITIES] == "layers missing: Not.There"
    assert statuses(results)[CheckName.WEB_MERCATOR] is CheckStatus.NOT_CHECKED


async def test_web_mercator_differing_from_the_catalogue_fails() -> None:
    entry = catastro_wms(web_mercator=False, sample=None)
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        results = await run(entry, mock)
    assert statuses(results)[CheckName.WEB_MERCATOR] is CheckStatus.FAILED
    assert "catalogue says not offered" in details(results)[CheckName.WEB_MERCATOR]


async def test_web_mercator_absent_as_recorded_passes() -> None:
    entry = catastro_wms(layers=["0"], web_mercator=False, sample=None)
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("igme_lithostrat_wms_capabilities.xml"), headers=XML
        )
        results = await run(entry, mock)
    assert statuses(results)[CheckName.WEB_MERCATOR] is CheckStatus.OK
    assert "needs the server's proxy" in details(results)[CheckName.WEB_MERCATOR]


async def test_a_rejected_request_fails_with_its_status() -> None:
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            400,
            content=fixture_bytes("catastro_rejected.html"),
            headers={"content-type": "text/html"},
        )
        results = await run(catastro_wms(), mock)
    assert details(results)[CheckName.CAPABILITIES] == "HTTP 400"
    assert details(results)[CheckName.SAMPLE] == "HTTP 400"
    # CORS is still read from a response, whatever its status.
    assert statuses(results)[CheckName.CORS] is CheckStatus.FAILED


async def test_malformed_capabilities_fail_the_check() -> None:
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("capabilities_truncated.xml"), headers=XML
        )
        results = await run(catastro_wms(sample=None), mock)
    assert statuses(results)[CheckName.CAPABILITIES] is CheckStatus.FAILED
    assert details(results)[CheckName.CAPABILITIES].startswith("not XML")


async def test_a_timeout_fails_every_check_and_leaves_cors_unchecked() -> None:
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).mock(side_effect=httpx.ConnectTimeout("slow"))
        results = await run(catastro_wms(), mock)
    assert statuses(results) == {
        CheckName.CAPABILITIES: CheckStatus.FAILED,
        CheckName.WEB_MERCATOR: CheckStatus.NOT_CHECKED,
        CheckName.SAMPLE: CheckStatus.FAILED,
        CheckName.CORS: CheckStatus.NOT_CHECKED,
    }
    assert "timed out" in details(results)[CheckName.SAMPLE]


async def test_a_service_exception_instead_of_an_image_fails_the_sample() -> None:
    with respx.mock as mock:
        mock.get(CATASTRO_WMS, params={"REQUEST": "GetCapabilities"}).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        mock.get(CATASTRO_WMS, params={"REQUEST": "GetMap"}).respond(
            200, content=fixture_bytes("catastro_wfs_not_found.xml"), headers=XML
        )
        results = await run(catastro_wms(), mock)
    assert statuses(results)[CheckName.SAMPLE] is CheckStatus.FAILED
    assert details(results)[CheckName.SAMPLE].startswith("expected image/png, got text/xml")


async def test_a_sample_without_the_expected_text_fails() -> None:
    sample = {
        "description": "the Obradoiro parcel",
        "params": {"STOREDQUERY_ID": "GetParcel"},
        "expect_content_type": "text/xml",
        "expect_text": "7279701NH3477G",
    }
    entry = service(
        id="catastro-wfs-parcels",
        kind="wfs",
        base_url=CATASTRO_WFS,
        layers=["cp:CadastralParcel"],
        sample=sample,
    )
    with respx.mock as mock:
        mock.get(CATASTRO_WFS, params={"REQUEST": "GetCapabilities"}).respond(
            200, content=fixture_bytes("catastro_wfs_capabilities.xml"), headers=XML
        )
        mock.get(CATASTRO_WFS, params={"STOREDQUERY_ID": "GetParcel"}).respond(
            200, content=fixture_bytes("catastro_wfs_not_found.xml"), headers=XML
        )
        results = await run(entry, mock)
    assert statuses(results)[CheckName.SAMPLE] is CheckStatus.FAILED
    assert "lacks '7279701NH3477G'" in details(results)[CheckName.SAMPLE]


async def test_a_found_parcel_passes_the_sample() -> None:
    sample = {
        "description": "the Obradoiro parcel",
        "path": "/query",
        "expect_content_type": "text/xml",
        "expect_text": "7279701NH3477G",
    }
    entry = service(kind="rest", base_url=CATASTRO_WFS, web_mercator=None, layers=[], sample=sample)
    with respx.mock as mock:
        mock.get(CATASTRO_WFS + "/query").respond(
            200, content=fixture_bytes("catastro_wfs_parcel.xml"), headers=XML
        )
        results = await run(entry, mock)
    assert statuses(results) == {CheckName.SAMPLE: CheckStatus.OK, CheckName.CORS: CheckStatus.OK}


async def test_cors_absent_as_recorded_passes_and_present_against_the_record_fails() -> None:
    sample = {"description": "json", "expect_content_type": "application/json"}
    entry = service(kind="rest", web_mercator=None, layers=[], sample=sample, cors=False)
    with respx.mock as mock:
        mock.get("https://wms.example.org/wms").respond(200, json={"ok": True})
        results = await run(entry, mock)
    assert statuses(results)[CheckName.CORS] is CheckStatus.OK
    with respx.mock as mock:
        mock.get("https://wms.example.org/wms").respond(
            200, json={"ok": True}, headers={"access-control-allow-origin": ORIGIN}
        )
        results = await run(entry, mock)
    assert statuses(results)[CheckName.CORS] is CheckStatus.FAILED
    assert (
        details(results)[CheckName.CORS] == "catalogue says not allowed, the service says allowed"
    )


async def test_a_service_that_needs_a_key_is_not_checked() -> None:
    sample = {"description": "tiles", "expect_content_type": "application/json"}
    entry = service(
        kind="rest", web_mercator=None, layers=[], sample=sample, needs_key=True, key_env="TEST_KEY"
    )
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get("https://wms.example.org/wms")
        results = await run(entry, mock)
    assert not route.called
    assert statuses(results) == {CheckName.SAMPLE: CheckStatus.NOT_CHECKED}
    assert "TEST_KEY" in details(results)[CheckName.SAMPLE]


# ── The whole catalogue ──────────────────────────────────────────────────────────────


async def test_the_catalogue_is_checked_service_by_service() -> None:
    other = service(id="other", base_url="https://tiles.example.org/wms", sample=None)
    sources = catalogue(catastro_wms(sample=None), other)
    with respx.mock as mock:
        mock.get(CATASTRO_WMS).respond(
            200, content=fixture_bytes("catastro_wms_capabilities.xml"), headers=XML
        )
        mock.get("https://tiles.example.org/wms").respond(503)
        async with CatalogueClient(sources, "0.1.0") as client:
            results = await check_catalogue(client, list(sources.services), ORIGIN)
    by_service = {(r.service_id, r.check): r.status for r in results}
    assert by_service[("catastro-wms", CheckName.CAPABILITIES)] is CheckStatus.OK
    assert by_service[("other", CheckName.CAPABILITIES)] is CheckStatus.FAILED


def test_the_table_has_one_row_per_check_and_a_summary() -> None:
    results = [
        CheckResult(service_id="a", check=CheckName.SAMPLE, status=CheckStatus.OK, detail="fine"),
        CheckResult(
            service_id="longer-id",
            check=CheckName.CORS,
            status=CheckStatus.FAILED,
            detail="catalogue says allowed",
        ),
    ]
    table = format_table(results).splitlines()
    assert table[0].split() == ["SERVICE", "CHECK", "STATUS", "DETAIL"]
    assert table[1].startswith("a          sample  ok")
    assert table[-1] == "1 ok, 1 failed, 0 not checked"
