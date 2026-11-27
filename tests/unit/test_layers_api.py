# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The official layers through the API: the tile proxy and the feature info of a tap."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from subphora.api import create_app
from subphora.config import Settings
from tests.support import FIXTURES, fast_settings, signed_in

type Handler = Callable[[httpx.Request], httpx.Response]

PNG = (FIXTURES / "layers" / "igme_lithostrat_export.png").read_bytes()


def layer_fixture(name: str) -> bytes:
    return (FIXTURES / "layers" / name).read_bytes()


class Upstream:
    """Every official service behind one httpx.MockTransport, answering ``handler``."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def answer(content: bytes, status: int = 200) -> Handler:
    return lambda _request: httpx.Response(status, content=content)


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


@asynccontextmanager
async def serve(
    settings: Settings, upstream: Upstream, root: Path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, root=root, transport=upstream.transport())
    async with app.router.lifespan_context(app), signed_in(app, settings, root) as client:
        yield client


# ── Tiles ──────────────────────────────────────────────────────────────────────────────

# A zoom-12 tile over the Ciudad Encantada (Cuenca).
CUENCA_TILE = "12/2025/1547"


async def test_a_layer_without_web_mercator_comes_from_its_arcgis_export_and_is_cached(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(answer(PNG))
    async with serve(settings, upstream, tmp_path) as client:
        first = await client.get(f"/api/layers/lithostratigraphy/tiles/{CUENCA_TILE}")
        second = await client.get(f"/api/layers/lithostratigraphy/tiles/{CUENCA_TILE}")
    assert first.status_code == second.status_code == 200
    assert first.headers["content-type"] == "image/png"
    assert first.headers["cache-control"] == "public, max-age=2592000"
    assert first.content == second.content == PNG
    (request,) = upstream.requests  # the second came from the cache
    assert request.url.host == "mapas.igme.es"
    assert request.url.path == (
        "/gis/rest/services/Cartografia_Tematica/IGME_Litoestratigrafico_200/MapServer/export"
    )
    params = request.url.params
    assert (params["bboxSR"], params["imageSR"], params["size"]) == ("3857", "3857", "256,256")
    assert (params["layers"], params["f"], params["format"]) == ("show:0", "image", "png32")
    west, south, east, north = (float(v) for v in params["bbox"].split(","))
    assert east - west == pytest.approx(north - south)
    assert east - west == pytest.approx(9783.94, abs=0.01)  # one zoom-12 tile
    assert west < -222_000 < east  # the Ciudad Encantada, in EPSG:3857 metres
    assert south < 4_895_000 < north


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/api/layers/nope/tiles/12/2025/1547", 404, "unknown_layer"),
        # MITECO has CORS and EPSG:3857: the browser calls it, the API does not relay it.
        ("/api/layers/groundwater-bodies/tiles/12/2025/1547", 404, "not_proxied"),
        ("/api/layers/lithostratigraphy/tiles/3/8/0", 400, "invalid_tile"),
        ("/api/layers/lithostratigraphy/tiles/10/505/385", 422, "outside_zoom_range"),
        ("/api/layers/lithostratigraphy/tiles/19/0/0", 422, "outside_zoom_range"),
    ],
)
async def test_a_tile_outside_the_catalogue_is_refused_without_calling_out(
    settings: Settings, tmp_path: Path, path: str, status: int, code: str
) -> None:
    upstream = Upstream(answer(PNG))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(path)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert upstream.requests == []


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


@pytest.mark.parametrize(
    ("handler", "status", "code"),
    [
        (answer(b"Internal error", 500), 502, "upstream_error"),
        (answer(layer_fixture("igme_exception.xml")), 502, "upstream_error"),
        (_timeout, 504, "upstream_timeout"),
    ],
)
async def test_a_tile_the_service_cannot_give_is_an_explicit_error(
    settings: Settings, tmp_path: Path, handler: Handler, status: int, code: str
) -> None:
    async with serve(settings, Upstream(handler), tmp_path) as client:
        response = await client.get(f"/api/layers/lithostratigraphy/tiles/{CUENCA_TILE}")
    assert response.status_code == status
    assert response.json()["code"] == code
    # Nothing unusable is cached.
    assert not any((tmp_path / "data" / "cache").rglob("*.bin"))


# ── Feature info ───────────────────────────────────────────────────────────────────────


def info(layer: str, lon: float, lat: float, zoom: float) -> str:
    return f"/api/layers/{layer}/info?lon={lon}&lat={lat}&zoom={zoom}"


async def test_a_tap_shows_only_the_allowed_fields_in_their_order(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(answer(layer_fixture("miteco_piezometer.json")))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("piezometers", -3.4316, 39.2537, 14))
    assert response.status_code == 200
    body = response.json()
    assert body["layer_id"] == "piezometers"
    (feature,) = body["features"]
    names = [field["name"] for field in feature["fields"]]
    assert names == [
        "Cód. Piezómetro",
        "Cód. Europeo",
        "Demarcación Hidrográfica",
        "Cota terreno (msnm)",
        "Profundidad obra (m)",
        "MASb controlada",
        "Condición",
        "Piezómetro",
    ]
    assert feature["fields"][0]["value"] == "04.04.207"
    # Fields outside the allowlist (here the place and the coordinates) never leave the API.
    assert "Municipio" not in response.text
    assert "Coordenada X" not in response.text
    assert body["source"]["service_id"] == "miteco-piezometers"
    assert body["source"]["attribution"].startswith("© Ministerio")
    (request,) = upstream.requests
    params = request.url.params
    assert (params["REQUEST"], params["QUERY_LAYERS"], params["CRS"]) == (
        "GetFeatureInfo",
        "RedPiezometrica",
        "EPSG:3857",
    )
    assert params["INFO_FORMAT"] == "application/json"
    assert params["I"] == params["J"] == str(int(params["WIDTH"]) // 2)
    west, _south, east, _north = (float(v) for v in params["BBOX"].split(","))
    # 21 pixels at zoom 14, where a 256-pixel tile is 2,445.98 m wide.
    assert east - west == pytest.approx(21 * 2445.98 / 256, rel=1e-4)


@pytest.mark.parametrize(
    ("layer", "fixture", "expected"),
    [
        (
            "magna-dip",
            "igme_magna_dip.json",
            [("Descripción", "Estratificación"), ("Dirección de buzamiento", "178")],
        ),
        ("permeability", "igme_permeability.xml", [("Permeabilidad", "MEDIA")]),
        (
            "geode-geology",
            "igme_geode_tenerife.json",
            [("Descripción Unidad Geológica", "Coladas basálticas")],
        ),
    ],
)
async def test_each_service_format_is_read(
    settings: Settings,
    tmp_path: Path,
    layer: str,
    fixture: str,
    expected: list[tuple[str, str]],
) -> None:
    upstream = Upstream(answer(layer_fixture(fixture)))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info(layer, -2.0, 40.17, 16))
    assert response.status_code == 200
    fields = {(f["name"], f["value"]) for f in response.json()["features"][0]["fields"]}
    assert set(expected) <= fields
    assert "OBJECTID" not in response.text


async def test_a_tap_on_nothing_is_an_empty_answer(settings: Settings, tmp_path: Path) -> None:
    upstream = Upstream(answer(layer_fixture("igme_geode_sea.json")))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("geode-geology", -4.5, 36.4, 13))
    assert response.status_code == 200
    assert response.json()["features"] == []


async def test_a_layer_without_web_mercator_is_asked_in_a_crs_it_offers(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(answer(layer_fixture("igme_permeability.xml")))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("lithostratigraphy", -2.0, 40.17, 13))
    assert response.status_code == 200
    params = upstream.requests[0].url.params
    assert params["CRS"] == "EPSG:4258"
    # Latitude first, as WMS 1.3.0 orders EPSG:4258.
    south, west, north, east = (float(v) for v in params["BBOX"].split(","))
    assert south < 40.17 < north
    assert west < -2.0 < east


@pytest.mark.parametrize(
    ("handler", "status", "code"),
    [
        (answer(b"Bad gateway", 502), 502, "upstream_error"),
        (answer(layer_fixture("igme_exception.xml")), 502, "upstream_error"),
        (answer(b"<html>maintenance</html>"), 502, "upstream_error"),
        (_timeout, 504, "upstream_timeout"),
    ],
)
async def test_a_tap_the_service_cannot_answer_is_an_explicit_error(
    settings: Settings, tmp_path: Path, handler: Handler, status: int, code: str
) -> None:
    async with serve(settings, Upstream(handler), tmp_path) as client:
        response = await client.get(info("magna-dip", -2.0, 40.17, 16))
    assert response.status_code == status
    assert response.json()["code"] == code
    assert not any((tmp_path / "data" / "cache").rglob("*.bin"))


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        (info("nope", -2.0, 40.17, 16), 404, "unknown_layer"),
        # SoilGrids answers no value to GetFeatureInfo: the layer has no tap.
        (info("soil-clay", -2.0, 40.17, 16), 404, "no_feature_info"),
        (info("water-points", -2.0, 40.17, 12), 422, "outside_zoom_range"),
    ],
)
async def test_a_tap_outside_the_catalogue_is_refused_without_calling_out(
    settings: Settings, tmp_path: Path, path: str, status: int, code: str
) -> None:
    upstream = Upstream(answer(b""))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(path)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert upstream.requests == []


async def test_a_tap_beyond_the_deepest_tiles_is_still_answered(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(answer(layer_fixture("igme_magna_dip.json")))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("magna-dip", -2.0, 40.17, 21))
    assert response.status_code == 200


async def test_a_tap_with_a_position_out_of_range_is_refused(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(answer(b""))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("magna-dip", -200.0, 40.17, 16))
    assert response.status_code == 422
    assert upstream.requests == []


async def test_the_map_is_served_without_calling_out(settings: Settings, tmp_path: Path) -> None:
    upstream = Upstream(answer(b""))
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get("/api/map")
    assert response.status_code == 200
    assert [base["id"] for base in response.json()["base_maps"]] == [
        "pnoa",
        "ign-base",
        "ign-base-grey",
    ]
    assert upstream.requests == []
