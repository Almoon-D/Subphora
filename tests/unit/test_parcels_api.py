# Copyright (c) 2026 Almoon-D. All rights reserved.
"""GET /api/parcels/{reference} end to end over a fake Catastro, and GET /api/map."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import yaml

from subphora.api import create_app
from subphora.config import Settings, load_settings
from tests.support import Catastro, fast_settings, fixture_bytes, parcel_fixture

SANTIAGO = "7279701NH3477G"


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


@asynccontextmanager
async def serve(
    settings: Settings, catastro: Catastro, root: Path
) -> AsyncIterator[httpx.AsyncClient]:
    """The app over ASGI, its lifespan run (Starlette's TestClient wants httpx2)."""
    app = create_app(settings, root=root, transport=catastro.transport())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def santiago() -> Catastro:
    return Catastro(
        wfs=parcel_fixture("wfs_santiago_4326.xml"), dnprc=parcel_fixture("dnprc_santiago.json")
    )


async def test_a_parcel_is_returned_in_epsg_4326(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, santiago(), tmp_path) as client:
        response = await client.get(f"/api/parcels/{SANTIAGO}")
    assert response.status_code == 200
    body = response.json()
    assert body["reference"] == SANTIAGO
    assert body["area_m2"] == 13352
    assert (body["municipality"], body["province"]) == ("SANTIAGO DE COMPOSTELA", "A CORUÑA")
    assert (body["province_code"], body["region_code"]) == ("ES-C", "ES-GA")
    assert body["geometry"]["type"] == "MultiPolygon"
    lon, lat = body["geometry"]["coordinates"][0][0][0]
    assert (lon, lat) == pytest.approx((-8.545248, 42.880433))
    west, south, east, north = body["bbox"]
    assert west < lon < east
    assert south < lat < north
    assert body["reference_point_local"]["crs"] == "EPSG:25829"
    assert [s["service_id"] for s in body["sources"]] == ["catastro-wfs-parcels", "catastro-ovc"]
    assert all(s["attribution"] == "Dirección General del Catastro" for s in body["sources"])


async def test_a_parcel_in_another_crs_is_reprojected(settings: Settings, tmp_path: Path) -> None:
    catastro = santiago()
    catastro.wfs = fixture_bytes("catastro_wfs_parcel.xml")  # answered in EPSG:25830
    async with serve(settings, catastro, tmp_path) as client:
        body = (await client.get(f"/api/parcels/{SANTIAGO}")).json()
    lon, lat = body["geometry"]["coordinates"][0][0][0]
    assert (lon, lat) == pytest.approx((-8.545248, 42.880433), abs=2e-6)


async def test_a_canary_parcel_is_measured_in_regcan95(settings: Settings, tmp_path: Path) -> None:
    catastro = Catastro(
        wfs=parcel_fixture("wfs_tinajo_4326.xml"), dnprc=parcel_fixture("dnprc_tinajo.json")
    )
    async with serve(settings, catastro, tmp_path) as client:
        body = (await client.get("/api/parcels/35029A03200314")).json()
    assert body["reference_point_local"]["crs"] == "EPSG:4083"
    assert len(body["geometry"]["coordinates"][0]) == 17
    assert body["region_code"] == "ES-CN"


async def test_the_answers_are_cached(settings: Settings, tmp_path: Path) -> None:
    catastro = santiago()
    async with serve(settings, catastro, tmp_path) as client:
        first = (await client.get(f"/api/parcels/{SANTIAGO}")).json()
        second = (await client.get(f"/api/parcels/{SANTIAGO}")).json()
    assert len(catastro.requests) == 2
    assert first == second
    assert sorted(p.name for p in tmp_path.joinpath("data", "cache").iterdir()) == [
        "catastro-ovc",
        "catastro-wfs-parcels",
    ]


async def test_a_not_found_answer_is_not_cached(settings: Settings, tmp_path: Path) -> None:
    catastro = Catastro(wfs=fixture_bytes("catastro_wfs_not_found.xml"))
    async with serve(settings, catastro, tmp_path) as client:
        for _ in range(2):
            response = await client.get("/api/parcels/29015A16799999")
            assert response.status_code == 404
            assert response.json()["code"] == "parcel_not_found"
    assert len(catastro.requests) == 2


async def test_a_malformed_reference_never_leaves_the_server(
    settings: Settings, tmp_path: Path
) -> None:
    catastro = santiago()
    async with serve(settings, catastro, tmp_path) as client:
        response = await client.get("/api/parcels/7279701NH3477G0001XX")
    assert response.status_code == 400
    assert response.json()["code"] == "malformed_reference"
    assert catastro.requests == []


@pytest.mark.parametrize("reference", ["31001A00100001", "01059A00100001", "48020A00100001"])
async def test_a_foral_rustic_reference_never_leaves_the_server(
    settings: Settings, tmp_path: Path, reference: str
) -> None:
    catastro = santiago()
    async with serve(settings, catastro, tmp_path) as client:
        response = await client.get(f"/api/parcels/{reference}")
    assert response.status_code == 422
    assert response.json()["code"] == "territory_not_supported"
    assert catastro.requests == []


async def test_an_urban_parcel_in_a_foral_province_is_not_supported(
    settings: Settings, tmp_path: Path
) -> None:
    navarra = parcel_fixture("dnprc_santiago.json").replace(b'"cp":"15"', b'"cp":"31"')
    catastro = Catastro(wfs=parcel_fixture("wfs_santiago_4326.xml"), dnprc=navarra)
    async with serve(settings, catastro, tmp_path) as client:
        response = await client.get(f"/api/parcels/{SANTIAGO}")
    assert response.status_code == 422
    assert response.json()["code"] == "territory_not_supported"


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("no answer", request=request)


def _reset(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection reset", request=request)


@pytest.mark.parametrize(
    ("catastro", "status", "code"),
    [
        (Catastro(wfs=_timeout), 504, "upstream_timeout"),
        (Catastro(wfs=_reset), 502, "upstream_error"),
        (Catastro(wfs=lambda _: httpx.Response(503, text="busy")), 502, "upstream_error"),
        (Catastro(wfs=b"<html>maintenance</html>"), 502, "upstream_error"),
        (
            Catastro(wfs=parcel_fixture("wfs_santiago_4326.xml"), dnprc=_timeout),
            504,
            "upstream_timeout",
        ),
        (
            Catastro(wfs=parcel_fixture("wfs_santiago_4326.xml"), dnprc=b"not json"),
            502,
            "upstream_error",
        ),
        (
            Catastro(
                wfs=parcel_fixture("wfs_santiago_4326.xml"),
                dnprc=parcel_fixture("dnprc_santiago.json").replace(b'"cp":"15"', b'"cp":"77"'),
            ),
            502,
            "upstream_error",
        ),
        (
            # A parcel placed east of Spain's UTM zones cannot be measured.
            Catastro(
                wfs=parcel_fixture("wfs_santiago_4326.xml").replace(b"-8.5", b"28.5"),
                dnprc=parcel_fixture("dnprc_santiago.json"),
            ),
            502,
            "upstream_error",
        ),
    ],
)
async def test_upstream_failures_are_explicit(
    settings: Settings, tmp_path: Path, catastro: Catastro, status: int, code: str
) -> None:
    async with serve(settings, catastro, tmp_path) as client:
        response = await client.get(f"/api/parcels/{SANTIAGO}")
    assert response.status_code == status
    assert response.json()["code"] == code
    assert not tmp_path.joinpath("data", "cache").exists()


async def test_the_map_layers_come_from_the_catalogue(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, santiago(), tmp_path) as client:
        body = (await client.get("/api/map")).json()
    (tiles,) = body["base"]["tiles"]
    assert tiles.startswith("https://www.ign.es/wmts/pnoa-ma?")
    assert tiles.endswith("tilematrix={z}&tilerow={y}&tilecol={x}")
    assert "tilematrixset=GoogleMapsCompatible" in tiles
    assert body["base"]["attribution"] == "PNOA CC-BY 4.0 scne.es"
    cadastre = body["cadastre"]
    assert cadastre["url"] == "https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx"
    assert cadastre["params"]["CRS"] == "EPSG:3857"
    assert cadastre["params"]["LAYERS"] == "CP.CadastralParcel"
    assert "BBOX" not in cadastre["params"]
    assert cadastre["attribution"] == "Dirección General del Catastro"
    assert cadastre["min_zoom"] > body["initial_view"]["zoom"]


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        ({"base": {"service": "nope"}}, "not in the catalogue"),
        ({"base": {"service": "catastro-wms"}}, "not a wmts"),
        ({"cadastre": {"layer": "XX"}}, "does not list layer"),
        ({"cadastre": {"service": "igme-lithostrat-wms", "layer": "x"}}, "does not list"),
    ],
)
def test_map_layers_must_be_drawable(
    config_dir: Path, edit: dict[str, object], message: str
) -> None:
    (config_dir / "owner.yaml").write_text(yaml.safe_dump({"map": edit}), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_settings(config_dir)


def test_a_map_layer_without_cors_is_refused(config_dir: Path) -> None:
    path = config_dir / "defaults" / "sources.yaml"
    text = path.read_text(encoding="utf-8")
    start = text.index("- id: catastro-wms")
    end = text.index("- id: catastro-wfs-parcels")
    path.write_text(
        text[:start] + text[start:end].replace("cors: true", "cors: false") + text[end:],
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="EPSG:3857 and CORS"):
        load_settings(config_dir)
