# Copyright (c) 2026 Almoon-D. All rights reserved.
"""GET /api/search and the /api/aoi routes end to end, over fake SIGPAC and CartoCiudad."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

from subphora.api import create_app
from subphora.config import Settings
from tests.support import FIXTURES, fast_settings

type Answer = bytes | Callable[[httpx.Request], httpx.Response]

SIGPAC = "sigpac-hubcloud.es"
CARTOCIUDAD = "www.cartociudad.es"
LISBON = (FIXTURES / "search" / "sigpac_point_lisbon.json").read_bytes()


def search_fixture(name: str) -> bytes:
    return (FIXTURES / "search" / name).read_bytes()


class Services:
    """Fake SIGPAC and CartoCiudad: answers by path prefix, every request recorded."""

    def __init__(self, answers: dict[str, Answer] | None = None) -> None:
        self.answers: dict[str, Answer] = answers or {}
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        for prefix, answer in self.answers.items():
            if path.startswith(prefix) or f"{request.url.host}{path}".startswith(prefix):
                return answer(request) if callable(answer) else httpx.Response(200, content=answer)
        raise AssertionError(f"unexpected request {request.url}")

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


ENCLOSURE = "/servicioconsultassigpac/query/recinfo/"
PARCEL = "/servicioconsultassigpac/query/recinfoparc/"
POINT = "/servicioconsultassigpac/query/recinfobypoint/"
CANDIDATES = "/geocoder/api/geocoder/candidates"
FIND = "/geocoder/api/geocoder/find"


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


@asynccontextmanager
async def serve(
    settings: Settings, services: Services, root: Path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, root=root, transport=services.transport())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def _search(client: httpx.AsyncClient, text: str) -> httpx.Response:
    return await client.get("/api/search", params={"q": text})


def _code(response: httpx.Response) -> str:
    code = response.json()["code"]
    assert isinstance(code, str)
    return code


# ── SIGPAC references ────────────────────────────────────────────────────────────────────


async def test_a_sigpac_enclosure_becomes_the_area(settings: Settings, tmp_path: Path) -> None:
    services = Services({ENCLOSURE: search_fixture("sigpac_enclosure_campos.geojson")})
    async with serve(settings, services, tmp_path) as client:
        answer = (await _search(client, "34-48-0-0-13-12-1")).json()
        (reading,) = answer["interpretations"]
        assert reading["kind"] == "sigpac"
        assert reading["origin"] == "sigpac_enclosure"
        assert reading["resolve"] == "/api/aoi/sigpac/34:48:0:0:13:12:1"
        assert services.requests == []  # reading the reference asks nobody
        area = (await client.get(reading["resolve"])).json()
    assert services.paths() == [f"{ENCLOSURE}34/48/0/0/13/12/1.geojson"]
    assert (area["origin"], area["label"]) == ("sigpac_enclosure", "34:48:0:0:13:12:1")
    assert area["area_m2"] == pytest.approx(62_744)
    assert (area["province"], area["province_code"], area["region_code"]) == (
        "Palencia",
        "ES-P",
        "ES-CL",
    )
    assert area["geometry"]["type"] == "MultiPolygon"
    lon, lat = area["geometry"]["coordinates"][0][0][0]
    assert (lon, lat) == pytest.approx((-4.953566, 41.948091), abs=1e-5)
    west, south, east, north = area["bbox"]
    assert west <= area["centre"][0] <= east
    assert south <= area["centre"][1] <= north
    assert area["centre_local"]["crs"] == "EPSG:25830"
    assert area["sources"][0]["attribution"] == "SIGPAC, FEGA, CC BY 4.0"
    assert area["parcel"] is None


async def test_a_sigpac_parcel_joins_its_enclosures(settings: Settings, tmp_path: Path) -> None:
    services = Services({PARCEL: search_fixture("sigpac_parcel_malaga.geojson")})
    async with serve(settings, services, tmp_path) as client:
        area = (await client.get("/api/aoi/sigpac/29:15:0:0:167:21")).json()
        again = (await client.get("/api/aoi/sigpac/29:15:0:0:167:21")).json()
    assert area["origin"] == "sigpac_parcel"
    assert len(area["geometry"]["coordinates"]) == 13
    assert area["area_m2"] == pytest.approx(17_526_519, rel=1e-6)
    assert area["province_code"] == "ES-MA"
    assert again == area
    assert len(services.requests) == 1  # cached


async def test_an_unknown_sigpac_reference_is_not_found_and_not_cached(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services({ENCLOSURE: search_fixture("sigpac_not_found.geojson")})
    async with serve(settings, services, tmp_path) as client:
        for _ in range(2):
            response = await client.get("/api/aoi/sigpac/29:15:0:0:167:99999:1")
            assert response.status_code == 404
            assert response.json()["code"] == "not_found"
            assert response.json()["source"] == "sigpac-queries"
    assert len(services.requests) == 2


async def test_a_malformed_sigpac_reference_never_leaves_the_server(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/sigpac/99:1:0:0:1:1:1")
        searched = await _search(client, "99:1:0:0:1:1:1")
    assert (response.status_code, _code(response)) == (400, "malformed_sigpac")
    assert (searched.status_code, _code(searched)) == (400, "malformed_sigpac")
    assert services.requests == []


def _sigpac_with(change: Callable[[dict[str, Any]], None]) -> bytes:
    import json

    body = json.loads(search_fixture("sigpac_enclosure_campos.geojson"))
    change(body)
    return json.dumps(body).encode()


@pytest.mark.parametrize(
    "answer",
    [
        b"not json",
        b"[]",
        _sigpac_with(lambda b: b.update(crs={"type": "EPSG", "properties": {"code": "25830"}})),
        _sigpac_with(lambda b: b["features"][0]["properties"].update(provincia=35)),
        _sigpac_with(lambda b: b["features"][0]["properties"].update(superficie=0)),
        _sigpac_with(lambda b: b["features"][0]["properties"].pop("recinto")),
        _sigpac_with(lambda b: b["features"][0].update(geometry={"type": "Point"})),
        _sigpac_with(lambda b: b["features"][0].update(geometry=None)),
        _sigpac_with(lambda b: b["features"].append("text")),
        _sigpac_with(lambda b: b["features"][0]["geometry"]["coordinates"][0].pop()),
        _sigpac_with(lambda b: b["features"][0]["geometry"].update(coordinates=[["x"]])),
        _sigpac_with(lambda b: b["features"][0]["geometry"].update(coordinates=[])),
        _sigpac_with(
            lambda b: b["features"][0]["geometry"].update(type="MultiPolygon", coordinates={})
        ),
        _sigpac_with(lambda b: b["features"][0]["geometry"].update(coordinates=[[["a", "b"]]])),
        # Positions outside any CRS (latitude 200): pyproj cannot take them.
        _sigpac_with(
            lambda b: b["features"][0]["geometry"].update(
                coordinates=[[[1, 200], [2, 200], [2, 201], [1, 200]]]
            )
        ),
        lambda _: httpx.Response(500, text="error"),
    ],
)
async def test_unusable_sigpac_answers_are_upstream_errors(
    settings: Settings, tmp_path: Path, answer: Answer
) -> None:
    services = Services({ENCLOSURE: answer})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/sigpac/34:48:0:0:13:12:1")
    assert (response.status_code, _code(response)) == (502, "upstream_error")
    assert response.json()["source"] == "sigpac-queries"
    assert not tmp_path.joinpath("data", "cache").exists()


async def test_a_sigpac_timeout_says_so(settings: Settings, tmp_path: Path) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no answer", request=request)

    services = Services({ENCLOSURE: slow})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/sigpac/34:48:0:0:13:12:1")
    assert (response.status_code, _code(response)) == (504, "upstream_timeout")


# ── places by name ───────────────────────────────────────────────────────────────────────


async def test_a_name_offers_cartociudads_places_of_the_configured_types(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services({CANDIDATES: search_fixture("cand_daimiel.json")})
    async with serve(settings, services, tmp_path) as client:
        answer = (await _search(client, "Daimiel")).json()
    readings = answer["interpretations"]
    assert [r["origin"] for r in readings] == ["place", "place", "municipality"] + ["street"] * 5
    municipality = readings[2]
    assert (municipality["label"], municipality["detail"]) == (
        "Daimiel, Ciudad Real",
        "Ciudad Real",
    )
    assert municipality["resolve"] == "/api/aoi/place?type=Municipio&id=13039"
    (request,) = services.requests
    assert request.url.params["q"] == "Daimiel"
    assert request.url.params["limit"] == str(settings.search.cartociudad.max_candidates)


async def test_a_municipality_becomes_its_outline(settings: Settings, tmp_path: Path) -> None:
    services = Services({FIND: search_fixture("find_daimiel_muni.json")})
    async with serve(settings, services, tmp_path) as client:
        area = (await client.get("/api/aoi/place?type=Municipio&id=13039")).json()
    assert services.requests[0].url.params["id"] == "13039"
    assert (area["origin"], area["label"]) == ("municipality", "Daimiel (Ciudad Real)")
    assert (area["municipality"], area["province_code"]) == ("Daimiel", "ES-CR")
    assert area["geometry"]["type"] == "MultiPolygon"
    # Daimiel's municipal term is about 439 km².
    assert area["area_m2"] == pytest.approx(439e6, rel=0.05)
    assert area["centre"] == pytest.approx([-3.6115055, 39.0675148])
    assert area["sources"][0]["attribution"] == "CartoCiudad CC-BY 4.0 scne.es"


async def test_an_address_becomes_a_point(settings: Settings, tmp_path: Path) -> None:
    services = Services(
        {
            CANDIDATES: search_fixture("cand_mayor_zaragoza.json"),
            FIND: search_fixture("find_portal_zaragoza.json"),
        }
    )
    async with serve(settings, services, tmp_path) as client:
        readings = (await _search(client, "calle mayor 1 zaragoza")).json()["interpretations"]
        assert {r["origin"] for r in readings} == {"address"}
        area = (await client.get(readings[1]["resolve"])).json()
    assert (area["origin"], area["label"]) == ("address", "CALLE MAYOR 1, Zaragoza")
    assert area["geometry"] == {
        "type": "Point",
        "coordinates": [-0.8773411536634814, 41.65416976320753],
    }
    assert area["area_m2"] is None
    assert area["centre_local"]["crs"] == "EPSG:25830"


async def test_a_street_becomes_its_centre(settings: Settings, tmp_path: Path) -> None:
    services = Services({FIND: search_fixture("find_street.json")})
    async with serve(settings, services, tmp_path) as client:
        area = (await client.get("/api/aoi/place?type=callejero&id=130390004129")).json()
    assert (area["origin"], area["label"]) == ("street", "CALLE DAIMIEL SUR, Daimiel")
    assert area["geometry"]["coordinates"] == pytest.approx([-3.5949513, 39.0573533])


async def test_a_name_nobody_knows(settings: Settings, tmp_path: Path) -> None:
    services = Services({CANDIDATES: search_fixture("cand_empty.json")})
    async with serve(settings, services, tmp_path) as client:
        response = await _search(client, "xqzzyvw")
    assert (response.status_code, _code(response)) == (404, "no_match")
    assert response.json()["source"] == "cartociudad"


async def test_candidates_of_other_types_are_dropped(settings: Settings, tmp_path: Path) -> None:
    postcode = b'[{"id":"13250","type":"Codpost","address":"13250","lat":0.0,"lng":0.0}]'
    services = Services({CANDIDATES: postcode})
    async with serve(settings, services, tmp_path) as client:
        response = await _search(client, "13250")
    assert _code(response) == "no_match"


async def test_an_unknown_place_is_not_found(settings: Settings, tmp_path: Path) -> None:
    services = Services({FIND: lambda _: httpx.Response(204)})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/place?type=Municipio&id=99999")
        other = await client.get("/api/aoi/place?type=Codpost&id=13250")
    assert (response.status_code, _code(response)) == (404, "not_found")
    assert (other.status_code, _code(other)) == (404, "not_found")
    assert len(services.requests) == 1  # a type not offered is not asked


def _find_with(**changes: Any) -> bytes:
    import json

    body = json.loads(search_fixture("find_daimiel_muni.json"))
    body.update(changes)
    return json.dumps(body).encode()


@pytest.mark.parametrize(
    "answer",
    [
        b"not json",
        b"[]",
        _find_with(provinceCode=None),
        _find_with(provinceCode="77"),
        _find_with(lat=None),
        _find_with(lat=0.0, lng=0.0),
        _find_with(geom="POINT(-3.6 39.0)"),  # a municipality without its outline
        _find_with(geom="not wkt at all ("),
        _find_with(geom="MULTIPOLYGON (((-3.6 39.0, -3.5 39.0, -3.5 39.1)))"),  # not closed
        _find_with(geom="POLYGON ((-3.6 39.0 5, -3.5 39.0 5, -3.5 39.1 5, -3.6 39.0 5))"),
        _find_with(geom="POLYGON ((-3.6 39.0, -3.5 39.0, -3.5 x, -3.6 39.0)"),
        _find_with(geom="POLYGON EMPTY"),
        _find_with(geom="POLYGON ((-3.6 39.0, -3.5 39.0)))"),
        _find_with(geom="POLYGON ((-3.6 200, -3.5 200, -3.5 201, -3.6 200))"),
        lambda _: httpx.Response(500, text="error"),
    ],
)
async def test_unusable_cartociudad_answers_are_upstream_errors(
    settings: Settings, tmp_path: Path, answer: Answer
) -> None:
    services = Services({FIND: answer})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/place?type=Municipio&id=13039")
    assert (response.status_code, _code(response)) == (502, "upstream_error")
    assert response.json()["source"] == "cartociudad"


@pytest.mark.parametrize(
    "answer",
    [
        b"{}",
        b'[{"id": "1"}]',
        b'["text"]',
    ],
)
async def test_unusable_candidates_are_upstream_errors(
    settings: Settings, tmp_path: Path, answer: bytes
) -> None:
    services = Services({CANDIDATES: answer})
    async with serve(settings, services, tmp_path) as client:
        response = await _search(client, "Daimiel")
    assert (response.status_code, _code(response)) == (502, "upstream_error")


# ── coordinates and drawn points ─────────────────────────────────────────────────────────


async def test_degrees_in_spain_give_one_reading(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: search_fixture("sigpac_point_daimiel.json")})
    async with serve(settings, services, tmp_path) as client:
        answer = (await _search(client, "39.0675, -3.6115")).json()
        (reading,) = answer["interpretations"]
        assert services.requests == []  # one reading needs no land check yet
        assert (reading["label"], reading["detail"]) == ("39.067500, -3.611500", "OGC:CRS84")
        assert reading["position"] == [-3.6115, 39.0675]
        area = (await client.get(reading["resolve"])).json()
    assert services.paths() == [f"{POINT}4258/-3.611500/39.067500.json"]
    assert (area["origin"], area["label"]) == ("coordinates", "39.067500, -3.611500")
    assert area["geometry"] == {"type": "Point", "coordinates": [-3.6115, 39.0675]}
    assert area["bbox"] == [-3.6115, 39.0675, -3.6115, 39.0675]
    assert (area["province"], area["land_checked"]) == ("Ciudad Real", True)
    assert area["sources"][0]["service_id"] == "sigpac-queries"


async def test_utm_with_its_zone(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: search_fixture("sigpac_point_daimiel.json")})
    async with serve(settings, services, tmp_path) as client:
        (reading,) = (await _search(client, "30S 447099 4324445")).json()["interpretations"]
        assert reading["detail"] == "EPSG:25830"
        assert reading["position"] == pytest.approx([-3.6115, 39.0675], abs=1e-5)
        area = (await client.get(reading["resolve"])).json()
    # The band was checked when the text was read; the area names the zone.
    assert area["label"] == "30 447099 4324445"
    assert area["centre_local"] == {
        "crs": "EPSG:25830",
        "x": pytest.approx(447099),
        "y": pytest.approx(4324445),
    }


async def test_utm_in_the_canaries_is_regcan95(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: search_fixture("sigpac_point_lanzarote.json")})
    async with serve(settings, services, tmp_path) as client:
        (reading,) = (await _search(client, "28R 633800 3211200")).json()["interpretations"]
        assert reading["detail"] == "EPSG:4083"
        area = (await client.get(reading["resolve"])).json()
    assert (area["province_code"], area["region_code"]) == ("ES-GC", "ES-CN")
    assert area["centre_local"]["crs"] == "EPSG:4083"


async def test_utm_without_a_zone_keeps_the_readings_on_land(
    settings: Settings, tmp_path: Path
) -> None:
    # In zone 30 the pair is Daimiel; in 31 it falls in the Mediterranean.
    def land_only_near_daimiel(request: httpx.Request) -> httpx.Response:
        lon = float(request.url.path.split("/")[-2])
        return httpx.Response(
            200, content=search_fixture("sigpac_point_daimiel.json") if lon < 0 else LISBON
        )

    services = Services({POINT: land_only_near_daimiel})
    async with serve(settings, services, tmp_path) as client:
        (reading,) = (await _search(client, "447099 4324445")).json()["interpretations"]
    assert reading["label"] == "30 447099 4324445"
    assert len(services.requests) == 2  # zones 30 and 31 fit the mainland box


async def test_utm_without_a_zone_offers_a_choice_where_both_are_land(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services({POINT: search_fixture("sigpac_point_daimiel.json")})
    async with serve(settings, services, tmp_path) as client:
        readings = (await _search(client, "447099 4324445")).json()["interpretations"]
    assert [r["detail"] for r in readings] == ["EPSG:25830", "EPSG:25831"]


async def test_a_land_check_that_fails_keeps_the_reading(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services({POINT: lambda _: httpx.Response(503)})
    async with serve(settings, services, tmp_path) as client:
        readings = (await _search(client, "447099 4324445")).json()["interpretations"]
    assert len(readings) == 2


async def test_no_reading_on_land(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: LISBON})
    async with serve(settings, services, tmp_path) as client:
        response = await _search(client, "447099 4324445")
    assert (response.status_code, _code(response)) == (422, "outside_country")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("51.5 -0.12", "outside_country"),  # London
        ("10 20", "outside_country"),
        ("28 447099 4324445", "wrong_utm_zone"),  # Daimiel's pair in the Canaries' zone
        ("29 447099 4324445", "wrong_utm_zone"),  # …or in zone 29: the Atlantic
        ("30T 447099 4324445", "wrong_utm_zone"),  # Daimiel is in band S
        ("33 447099 4324445", "wrong_utm_zone"),
        ("30 447099 1324445", "outside_country"),  # no zone puts it in Spain
        ("40°61'N 3°W", "malformed_coordinates"),
    ],
)
async def test_coordinates_outside_spain_or_in_the_wrong_zone(
    settings: Settings, tmp_path: Path, text: str, code: str
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        response = await _search(client, text)
    assert _code(response) == code, response.json()
    assert response.status_code == (400 if code.startswith("malformed") else 422)
    assert services.requests == []


async def test_a_point_at_sea_is_outside_spain(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: LISBON})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get(
            "/api/aoi/point",
            params={"crs": "OGC:CRS84", "x": -3.6, "y": 36.3, "origin": "drawn_point"},
        )
    assert (response.status_code, _code(response)) == (422, "outside_country")
    assert response.json()["source"] == "sigpac-queries"


async def test_a_point_in_ceuta_is_placed_by_its_box(settings: Settings, tmp_path: Path) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        area = (
            await client.get(
                "/api/aoi/point",
                params={"crs": "OGC:CRS84", "x": -5.318, "y": 35.888, "origin": "drawn_point"},
            )
        ).json()
    assert services.requests == []
    assert (area["origin"], area["label"]) == ("drawn_point", "35.888000, -5.318000")
    assert (area["province"], area["province_code"], area["region_code"]) == (
        "Ceuta",
        "ES-CE",
        "ES-CE",
    )
    assert (area["land_checked"], area["sources"]) == (False, [])


@pytest.mark.parametrize(
    "params",
    [
        {"crs": "EPSG:3857", "x": "1", "y": "2", "origin": "coordinates"},
        {"crs": "OGC:CRS84", "x": "-3.6", "y": "39.0", "origin": "sigpac_parcel"},
    ],
)
async def test_points_in_other_crss_or_origins_are_refused(
    settings: Settings, tmp_path: Path, params: dict[str, str]
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        response = await client.get("/api/aoi/point", params=params)
    assert (response.status_code, _code(response)) == (400, "malformed_coordinates")


async def test_a_bad_land_check_answer_is_an_upstream_error(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services({POINT: b'[{"municipio": 1}]'})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get(
            "/api/aoi/point",
            params={"crs": "OGC:CRS84", "x": -3.6115, "y": 39.0675, "origin": "drawn_point"},
        )
        other = await client.get(
            "/api/aoi/point",
            params={"crs": "OGC:CRS84", "x": -3.6115, "y": 39.0676, "origin": "drawn_point"},
        )
    assert _code(response) == "upstream_error"
    assert _code(other) == "upstream_error"


@pytest.mark.parametrize("answer", [b"{}", b"nope", b'[{"provincia": 99}]'])
async def test_unusable_land_checks(settings: Settings, tmp_path: Path, answer: bytes) -> None:
    services = Services({POINT: answer})
    async with serve(settings, services, tmp_path) as client:
        response = await client.get(
            "/api/aoi/point",
            params={"crs": "OGC:CRS84", "x": -3.6115, "y": 39.0675, "origin": "drawn_point"},
        )
    assert (response.status_code, _code(response)) == (502, "upstream_error")


# ── drawn polygons ───────────────────────────────────────────────────────────────────────

DRAWN = [[-3.62, 39.06], [-3.60, 39.06], [-3.60, 39.075], [-3.62, 39.075], [-3.62, 39.06]]


def _polygon(ring: list[list[float]]) -> dict[str, Any]:
    return {"type": "Polygon", "coordinates": [ring]}


async def test_a_drawn_polygon_becomes_the_area(settings: Settings, tmp_path: Path) -> None:
    services = Services({POINT: search_fixture("sigpac_point_daimiel.json")})
    async with serve(settings, services, tmp_path) as client:
        response = await client.post("/api/aoi/polygon", json=_polygon(DRAWN))
    assert response.status_code == 200
    area = response.json()
    assert (area["origin"], area["label"]) == ("drawn_polygon", None)
    assert area["geometry"]["coordinates"] == [[DRAWN]]
    # 0.02° by 0.015° at 39° N: about 1.73 km by 1.67 km.
    assert area["area_m2"] == pytest.approx(2.88e6, rel=0.01)
    assert area["centre"] == pytest.approx([-3.61, 39.0675])
    assert area["province_code"] == "ES-CR"
    # The land check asks SIGPAC at the point inside.
    assert services.paths() == [f"{POINT}4258/-3.610000/39.067500.json"]


@pytest.mark.parametrize(
    "body",
    [
        {"type": "Point", "coordinates": [-3.6, 39.0]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [DRAWN, DRAWN]},  # a hole
        {"type": "Polygon", "coordinates": [[["a", "b"]]]},
        _polygon(DRAWN[:-1]),  # not closed
        _polygon(
            [[-3.62, 39.06], [-3.60, 39.075], [-3.60, 39.06], [-3.62, 39.075], [-3.62, 39.06]]
        ),
        _polygon(
            [[-3.62 + i * 1e-5, 39.06 + (i % 2) * 1e-5] for i in range(300)] + [[-3.62, 39.06]]
        ),
    ],
)
async def test_an_invalid_drawn_polygon(
    settings: Settings, tmp_path: Path, body: dict[str, Any]
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        response = await client.post("/api/aoi/polygon", json=body)
    assert (response.status_code, _code(response)) == (400, "invalid_polygon")
    assert services.requests == []


async def test_a_body_that_is_not_json(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, Services(), tmp_path) as client:
        response = await client.post("/api/aoi/polygon", content=b"not json")
    assert _code(response) == "invalid_polygon"


@pytest.mark.parametrize(
    "ring",
    [
        # Crossing from Spain into Portugal's longitudes beyond the mainland box.
        [[-9.5, 42.0], [-8.0, 42.0], [-8.0, 42.5], [-9.5, 42.0]],
        # From the mainland to Ceuta.
        [[-5.3, 35.9], [-5.3, 36.2], [-5.0, 36.2], [-5.3, 35.9]],
    ],
)
async def test_a_drawn_polygon_lies_in_one_territory(
    settings: Settings, tmp_path: Path, ring: list[list[float]]
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        response = await client.post("/api/aoi/polygon", json=_polygon(ring))
    assert (response.status_code, _code(response)) == (422, "outside_country")


# ── the search box itself ────────────────────────────────────────────────────────────────


async def test_an_empty_search(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, Services(), tmp_path) as client:
        response = await _search(client, "   ")
    assert (response.status_code, _code(response)) == (400, "empty_query")


async def test_a_cadastral_reference_is_read_without_asking_catastro(
    settings: Settings, tmp_path: Path
) -> None:
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        (reading,) = (await _search(client, "7279701 NH3477G 0001 SJ")).json()["interpretations"]
    assert reading == {
        "kind": "cadastral",
        "origin": "cadastral",
        "label": "7279701NH3477G",
        "detail": None,
        "position": None,
        "resolve": "/api/aoi/cadastral/7279701NH3477G",
    }
    assert services.requests == []


async def test_an_ambiguous_text_offers_each_reading(settings: Settings, tmp_path: Path) -> None:
    # Six numbers: a SIGPAC parcel in Segovia, and 40°25'0" 3°42'13" (east: the sea off
    # Mallorca, which the box holds; the reversed order is no latitude in Spain).
    services = Services()
    async with serve(settings, services, tmp_path) as client:
        readings = (await _search(client, "40 25 0 3 42 13")).json()["interpretations"]
    assert [r["kind"] for r in readings] == ["sigpac", "coordinates"]
    assert services.requests == []


async def test_utm_values_pyproj_cannot_take(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, Services(), tmp_path) as client:
        response = await client.get(
            "/api/aoi/point",
            params={"crs": "EPSG:25830", "x": "inf", "y": "4000000", "origin": "coordinates"},
        )
    assert _code(response) == "outside_country"
