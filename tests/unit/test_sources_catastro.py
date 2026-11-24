# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Parsers of Catastro's answers: real fixtures, then every malformed variant."""

import json

import pytest

from subphora.domain.parcels import LookupFailure, ParcelLookupError
from subphora.sources.catastro import epsg_of, parse_dnprc, parse_wfs_parcel, wfs_parcel_params
from tests.support import fixture_bytes, parcel_fixture

SANTIAGO = "7279701NH3477G"
TINAJO = "35029A03200314"

_WFS_HEAD = (
    '<FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" '
    'xmlns:gml="http://www.opengis.net/gml/3.2" '
    'xmlns:cp="http://inspire.ec.europa.eu/schemas/cp/4.0">'
)
_RING = "0 0 0 1 1 1 0 0"


def wfs(
    *,
    area: str | None = "100",
    geometry: str | None = None,
    point: str | None = '<gml:Point srsName="EPSG:25830"><gml:pos>0.5 0.5</gml:pos></gml:Point>',
    reference: str = SANTIAGO,
) -> bytes:
    if geometry is None:
        geometry = (
            '<gml:MultiSurface srsName="EPSG:25830"><gml:surfaceMember><gml:Surface>'
            "<gml:patches><gml:PolygonPatch><gml:exterior><gml:LinearRing>"
            f"<gml:posList>{_RING}</gml:posList>"
            "</gml:LinearRing></gml:exterior></gml:PolygonPatch></gml:patches>"
            "</gml:Surface></gml:surfaceMember></gml:MultiSurface>"
        )
    parts = [_WFS_HEAD, "<member><cp:CadastralParcel>"]
    if area is not None:
        parts.append(f'<cp:areaValue uom="m2">{area}</cp:areaValue>')
    parts.append(f"<cp:geometry>{geometry}</cp:geometry>")
    parts.append(f"<cp:nationalCadastralReference>{reference}</cp:nationalCadastralReference>")
    if point is not None:
        parts.append(f"<cp:referencePoint>{point}</cp:referencePoint>")
    parts.append("</cp:CadastralParcel></member></FeatureCollection>")
    return "".join(parts).encode()


def surface(pos_list: str, attrs: str = "", inner: str = "") -> str:
    return (
        '<gml:MultiSurface srsName="EPSG:25830"><gml:surfaceMember>'
        f"<gml:Surface {attrs}><gml:patches><gml:PolygonPatch><gml:exterior><gml:LinearRing>"
        f"{pos_list}</gml:LinearRing></gml:exterior>{inner}</gml:PolygonPatch></gml:patches>"
        "</gml:Surface></gml:surfaceMember></gml:MultiSurface>"
    )


def test_the_request_asks_for_one_parcel_in_epsg_4326() -> None:
    params = wfs_parcel_params(SANTIAGO)
    assert params["STOREDQUERY_ID"] == "GetParcel"
    assert params["refcat"] == SANTIAGO
    assert params["srsname"] == "EPSG::4326"


def test_a_parcel_in_epsg_4326_keeps_latitude_first() -> None:
    raw = parse_wfs_parcel(parcel_fixture("wfs_santiago_4326.xml"), SANTIAGO)
    assert raw.srs == "EPSG:4326"
    assert raw.area_m2 == 13352
    assert len(raw.polygons) == 1
    assert raw.polygons[0][0][0] == (42.880433, -8.545248)
    assert raw.reference_point_srs == "EPSG:4326"


def test_a_parcel_answered_in_another_crs_reports_that_crs() -> None:
    raw = parse_wfs_parcel(fixture_bytes("catastro_wfs_parcel.xml"), SANTIAGO)
    assert raw.srs == "EPSG:25830"
    assert raw.reference_point == (47127.41, 4762495.08)


def test_holes_are_kept_after_the_outer_ring() -> None:
    raw = parse_wfs_parcel(parcel_fixture("wfs_tinajo_4326.xml"), TINAJO)
    assert raw.area_m2 == 23614448
    assert [len(polygon) for polygon in raw.polygons] == [17]


def test_a_plain_polygon_member_is_read() -> None:
    geometry = (
        '<gml:MultiSurface srsName="EPSG:25830"><gml:surfaceMember><gml:Polygon>'
        f"<gml:exterior><gml:LinearRing><gml:posList>{_RING}</gml:posList></gml:LinearRing>"
        "</gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>"
    )
    raw = parse_wfs_parcel(wfs(geometry=geometry), SANTIAGO)
    assert raw.polygons == ((((0, 0), (0, 1), (1, 1), (0, 0)),),)


def test_not_found_is_its_own_failure() -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_wfs_parcel(fixture_bytes("catastro_wfs_not_found.xml"), "29015A16799999")
    assert caught.value.failure is LookupFailure.NOT_FOUND


def test_an_empty_collection_is_not_found() -> None:
    empty = (_WFS_HEAD + "</FeatureCollection>").encode()
    with pytest.raises(ParcelLookupError) as caught:
        parse_wfs_parcel(empty, SANTIAGO)
    assert caught.value.failure is LookupFailure.NOT_FOUND


def test_another_parcel_is_not_this_one() -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_wfs_parcel(wfs(reference="0910001QD3101S"), SANTIAGO)
    assert caught.value.failure is LookupFailure.NOT_FOUND


def test_catastro_rejecting_the_reference_is_malformed() -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_wfs_parcel(parcel_fixture("wfs_invalid_length.xml"), "12345")
    assert caught.value.failure is LookupFailure.MALFORMED


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (fixture_bytes("capabilities_truncated.xml"), "malformed XML"),
        (b"<html><body>error</body></html>", "unexpected answer"),
        (
            b'<ExceptionReport xmlns="http://www.opengis.net/ows/1.1"><Exception>'
            b"<ExceptionText>Server busy</ExceptionText></Exception></ExceptionReport>",
            "Server busy",
        ),
        (
            b'<ExceptionReport xmlns="http://www.opengis.net/ows/1.1"></ExceptionReport>',
            "no text",
        ),
        (wfs(area=None), "areaValue"),
        (wfs(area="n/a"), "areaValue"),
        (wfs(area="0"), "areaValue"),
        (wfs(geometry=""), "MultiSurface"),
        (wfs(geometry="<gml:MultiSurface/>"), "srsName"),
        (wfs(geometry='<gml:MultiSurface srsName="EPSG:25830"/>'), "no polygon"),
        (wfs(geometry='<gml:MultiSurface srsName="CRS:84"/>'), "srsName"),
        (wfs(geometry=surface("<gml:posList>0 0 1 1 0 0</gml:posList>")), "not closed"),
        (wfs(geometry=surface("<gml:posList>0 0 0 1 1 1 0 1</gml:posList>")), "not closed"),
        (wfs(geometry=surface("<gml:posList>0 0 0 1 1</gml:posList>")), "odd number"),
        (wfs(geometry=surface("<gml:posList>0 0 a b 1 1 0 0</gml:posList>")), "non-numeric"),
        (wfs(geometry=surface("<gml:posList/>")), "exterior ring"),
        (
            wfs(geometry=surface('<gml:posList srsDimension="3">0 0 0 0 1 0 1 1 0</gml:posList>')),
            "srsDimension",
        ),
        (
            wfs(geometry=surface(f"<gml:posList>{_RING}</gml:posList>", 'srsName="EPSG:4326"')),
            "inside a MultiSurface",
        ),
        (wfs(point=None), "reference point"),
        (wfs(point="<gml:Point/>"), "reference point"),
        (wfs(point="<gml:Point><gml:pos>1 2 3 4</gml:pos></gml:Point>"), "reference point"),
    ],
)
def test_a_bad_answer_is_an_upstream_failure(body: bytes, message: str) -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_wfs_parcel(body, SANTIAGO)
    assert caught.value.failure is LookupFailure.UPSTREAM_ERROR
    assert message in caught.value.detail


def test_a_hole_is_read() -> None:
    hole = (
        "<gml:interior><gml:LinearRing><gml:posList>0.1 0.1 0.1 0.2 0.2 0.2 0.1 0.1"
        "</gml:posList></gml:LinearRing></gml:interior>"
    )
    geometry = surface(f"<gml:posList>{_RING}</gml:posList>", inner=hole)
    raw = parse_wfs_parcel(wfs(geometry=geometry), SANTIAGO)
    assert len(raw.polygons[0]) == 2


@pytest.mark.parametrize(
    ("name", "epsg"),
    [
        ("http://www.opengis.net/def/crs/EPSG/0/4326", "EPSG:4326"),
        ("urn:ogc:def:crs:EPSG::25830", "EPSG:25830"),
        ("urn:ogc:def:crs:EPSG:6.6:4258", "EPSG:4258"),
        ("EPSG::4083", "EPSG:4083"),
        (" EPSG:25829 ", "EPSG:25829"),
    ],
)
def test_srs_names(name: str, epsg: str) -> None:
    assert epsg_of(name) == epsg


@pytest.mark.parametrize(
    ("name", "place"),
    [
        ("dnprc_santiago.json", ("SANTIAGO DE COMPOSTELA", "A CORUÑA", "15")),
        ("dnprc_tinajo.json", ("TINAJO", "LAS PALMAS", "35")),
        ("dnprc_atocha_several.json", ("MADRID", "MADRID", "28")),
    ],
)
def test_the_place_of_a_parcel(name: str, place: tuple[str, str, str]) -> None:
    found = parse_dnprc(parcel_fixture(name), "x")
    assert (found.municipality, found.province, found.province_code) == place


def test_no_property_is_not_found() -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_dnprc(parcel_fixture("dnprc_not_found.json"), "29015A16799999")
    assert caught.value.failure is LookupFailure.NOT_FOUND


def _dnprc(result: object) -> bytes:
    return json.dumps({"consulta_dnprcResult": result}).encode()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<html/>", "malformed JSON"),
        (b"{}", "malformed JSON"),
        (b"[]", "malformed JSON"),
        (_dnprc([]), "unexpected document"),
        (_dnprc({"lerr": [{"cod": "43", "des": "busy"}]}), "['43']"),
        (_dnprc({"control": {}}), "without a location"),
        (_dnprc({"lrcdnp": {"rcdnp": []}}), "without a location"),
        (_dnprc({"bico": {"bi": {"dt": "x"}}}), "without a location"),
        (_dnprc({"bico": {"bi": {"dt": {"nm": "X"}}}}), "no municipality"),
        (_dnprc({"bico": {"bi": {"dt": {"nm": "X", "np": "Y", "loine": "1"}}}}), "no municipality"),
        (
            _dnprc({"bico": {"bi": {"dt": {"nm": " ", "np": "Y", "loine": {"cp": "1"}}}}}),
            "empty",
        ),
    ],
)
def test_a_bad_property_answer_is_an_upstream_failure(body: bytes, message: str) -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_dnprc(body, "x")
    assert caught.value.failure is LookupFailure.UPSTREAM_ERROR
    assert message in caught.value.detail


def test_a_one_digit_province_code_is_padded() -> None:
    body = _dnprc({"bico": {"bi": {"dt": {"nm": "MERIDA", "np": "BADAJOZ", "loine": {"cp": 6}}}}})
    assert parse_dnprc(body, "x").province_code == "06"
