# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Regional detail over the national layers (decision 0023): the qualification rule, the
official boundaries, and a tap that asks the regional layer first and falls back."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from subphora.api import create_app
from subphora.api.map import map_config
from subphora.config import Settings, load_settings
from subphora.config.regional import Evidence, QualificationRule, qualification_failures
from subphora.domain.layers import LayerDetail
from subphora.geo.areas import BoundaryError, contains, round_to_grid
from subphora.sources.boundaries import BoundaryParseError, boundary_params, parse_boundary
from tests.support import FIXTURES, fast_settings

# ── The rule ─────────────────────────────────────────────────────────────────────────────

RULE = QualificationRule(
    official_only=True,
    max_years_older=0,
    metres_per_scale_unit=0.0005,
    finer_than_ratio=1.0,
    legal_themes=["groundwater-at-risk", "public-water-domain"],
)
SOILGRIDS = LayerDetail(cell_m=250, edition=2021)


def evidence(**change: Any) -> Evidence:
    values: dict[str, Any] = {
        "official": True,
        "detail": LayerDetail(scale_denominator=25000, edition=2023),
        "adds": None,
        "clip_of_national": False,
        "competent_authority": False,
    }
    values.update(change)
    return Evidence(**values)


def test_a_finer_official_recent_layer_qualifies() -> None:
    # 1:25,000 resolves about 12.5 m, finer than SoilGrids' 250 m cells.
    assert qualification_failures(RULE, "soil-clay", evidence(), SOILGRIDS) == []


def test_a_layer_as_detailed_as_the_national_one_qualifies_only_if_richer() -> None:
    same = LayerDetail(scale_denominator=25000, edition=2021)
    assert qualification_failures(RULE, "soil-clay", evidence(), same) == [
        "it is neither finer than the national layer nor richer in attributes"
    ]
    assert qualification_failures(RULE, "soil-clay", evidence(adds="soil series"), same) == []


@pytest.mark.parametrize(
    ("change", "national", "failure"),
    [
        ({"official": False}, SOILGRIDS, "it is not an official service"),
        ({"clip_of_national": True, "adds": "x"}, SOILGRIDS, "it is a clip of the national layer"),
        (
            {"detail": LayerDetail(scale_denominator=25000, edition=2005)},
            SOILGRIDS,
            "its edition 2005 is older than the national 2021",
        ),
        (
            {"detail": LayerDetail(scale_denominator=25000)},
            SOILGRIDS,
            "its edition is not stated",
        ),
        (
            {},
            LayerDetail(scale_denominator=50000),
            "the national edition is not stated, so it cannot be shown as recent",
        ),
        (
            # 1:1,000,000 resolves about 500 m: coarser than SoilGrids' 250 m cells.
            {"detail": LayerDetail(scale_denominator=1000000, edition=2023)},
            SOILGRIDS,
            "it is neither finer than the national layer nor richer in attributes",
        ),
    ],
)
def test_a_layer_that_fails_the_rule_says_why(
    change: dict[str, Any], national: LayerDetail, failure: str
) -> None:
    assert failure in qualification_failures(RULE, "soil-clay", evidence(**change), national)


def test_a_legal_status_comes_only_from_the_competent_authority() -> None:
    richer = evidence(adds="preventive control", detail=LayerDetail(edition=2023))
    national = LayerDetail(edition=2023)
    assert qualification_failures(RULE, "groundwater-at-risk", richer, national) == [
        "its publisher is not the competent authority for this legal status"
    ]
    competent = richer.model_copy(update={"competent_authority": True})
    assert qualification_failures(RULE, "groundwater-at-risk", competent, national) == []


def edit_regional(config_dir: Path, change: Any) -> None:
    path = config_dir / "defaults" / "regional.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def regional_layer(data: dict[str, Any], layer_id: str) -> dict[str, Any]:
    return next(layer for layer in data["layers"] if layer["id"] == layer_id)


def test_every_regional_layer_in_the_configuration_qualifies() -> None:
    settings = load_settings()
    assert {layer.id for layer in settings.regional.layers} == {
        "navarra-soils",
        "catalonia-hydrogeology",
        "andalusia-preventive-control",
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: regional_layer(d, "navarra-soils")["evidence"]["detail"].update(edition=2005),
            "navarra-soils does not qualify: its edition 2005 is older than the national 2021",
        ),
        (
            lambda d: regional_layer(d, "andalusia-preventive-control")["evidence"].update(
                competent_authority=False
            ),
            "not the competent authority",
        ),
        (
            lambda d: regional_layer(d, "navarra-soils").update(theme="nope"),
            "theme 'nope' is not a map overlay",
        ),
        (lambda d: regional_layer(d, "navarra-soils").update(id="soil-clay"), "a map overlay's"),
        (
            lambda d: regional_layer(d, "navarra-soils").update(areas=["ES-CT"]),
            "idena-wms does not cover ES-CT",
        ),
        (lambda d: regional_layer(d, "navarra-soils").update(areas=["ES-XX"]), "unknown areas"),
        (lambda d: regional_layer(d, "navarra-soils").update(layer="XX"), "does not list layer"),
        (
            lambda d: regional_layer(d, "navarra-soils").update(
                service="igme-lithostrat-wms", layer="0"
            ),
            "lacks EPSG:3857",
        ),
        (lambda d: regional_layer(d, "navarra-soils").update(min_zoom=20), "max_zoom"),
        (lambda d: d["areas"].append(d["areas"][0]), "duplicate area ids"),
        (lambda d: d["areas"][0].update(id="Navarra"), "not an ISO 3166-2 region"),
        (lambda d: d["areas"][0].update(bbox=[1, 1, 0, 0]), "west, south, east, north"),
        (
            lambda d: d["boundaries"]["sources"]["region"].update(service="idena-wms"),
            "not a wfs",
        ),
        (lambda d: d["boundaries"]["sources"].pop("district"), "no boundary source for kind"),
    ],
)
def test_a_regional_layer_that_does_not_fit_stops_the_settings(
    config_dir: Path, change: Any, message: str
) -> None:
    edit_regional(config_dir, change)
    with pytest.raises(ValueError, match=message):
        load_settings(config_dir)


def test_the_map_lists_each_theme_with_its_regional_layers() -> None:
    config = map_config(load_settings())
    themes = {overlay.id: overlay for overlay in config.overlays}
    (soils,) = themes["soil-clay"].regional
    assert soils.id == "navarra-soils"
    assert soils.area_ids == ("ES-NC",)
    assert soils.bounds == (-2.51, 41.90, -0.72, 43.32)
    assert soils.detail == LayerDetail(scale_denominator=25000, edition=2023)
    assert soils.tiles[0].startswith("https://idena.navarra.es/ogc/wms?")
    assert not soils.proxied
    assert themes["soil-clay"].detail == LayerDetail(cell_m=250, edition=2021)
    # REDIAM has no CORS: the API's proxy draws it, and it covers three districts.
    (andalusia,) = themes["groundwater-at-risk"].regional
    assert andalusia.proxied
    assert andalusia.tiles == ("/api/layers/andalusia-preventive-control/tiles/{z}/{x}/{y}",)
    assert andalusia.area_ids == ("ES060", "ES063", "ES064")
    assert andalusia.bounds == (-7.36, 35.98, -1.70, 37.91)
    assert {o.id for o in config.overlays if o.regional} == {
        "soil-clay",
        "groundwater-at-risk",
        "hydrogeology",
    }


# ── Boundaries ───────────────────────────────────────────────────────────────────────────


def square(west: float, south: float, east: float, north: float) -> dict[str, Any]:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def test_two_areas_sharing_a_border_hold_every_point_of_it_exactly_once() -> None:
    grid = 0.0001
    left = round_to_grid(square(0, 0, 1, 1), grid)
    right = round_to_grid(square(1, 0, 2, 1), grid)
    above = round_to_grid(square(0, 1, 1, 2), grid)
    for point in [(1.0, 0.5), (1.0, 0.0), (0.5, 1.0), (1.0, 1.0)]:
        holders = [area for area in (left, right, above) if contains(area, *point)]
        assert len(holders) <= 1, point
    assert contains(left, 0.99999, 0.5)
    assert contains(right, 1.00001, 0.5)
    assert not contains(left, 1.00001, 0.5)
    # Exactly one of the two holds a point on their shared border.
    assert contains(left, 1.0, 0.5) != contains(right, 1.0, 0.5)
    assert contains(left, 0.5, 1.0) != contains(above, 0.5, 1.0)


def test_rounding_keeps_a_shared_border_shared() -> None:
    # Two areas meeting along a wiggly border, its vertices off the grid.
    border = [[1.00003, 0.0], [1.00234, 0.31234], [0.99766, 0.62345], [1.00001, 1.0]]
    west = {"type": "Polygon", "coordinates": [[[0, 0], *border, [0, 1], [0, 0]]]}
    east = {"type": "Polygon", "coordinates": [[*border, [2, 1], [2, 0], border[0]]]}
    grid = 0.0001
    west_vertices = {v for polygon in round_to_grid(west, grid) for r in polygon for v in r}
    east_vertices = {v for polygon in round_to_grid(east, grid) for r in polygon for v in r}
    assert {
        (1.0, 0.0),
        (1.0023, 0.3123),
        (0.9977, 0.6234),
        (1.0, 1.0),
    } <= west_vertices & east_vertices


def test_rounding_drops_what_collapses_and_collinear_vertices() -> None:
    islet = [[5, 5], [5.00001, 5], [5.00001, 5.00001], [5, 5]]
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [0.5, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [islet],
        ],
    }
    ((outer,),) = round_to_grid(geometry, 0.0001)
    assert outer == ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [0, 0]},
        {"type": "Polygon"},
        {"type": "Polygon", "coordinates": [[[0, 0], [0.00001, 0], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0], [1], [2]]]},
        [],
    ],
)
def test_a_boundary_that_is_not_an_area_is_refused(geometry: Any) -> None:
    with pytest.raises(BoundaryError):
        round_to_grid(geometry, 0.0001)


def test_a_boundary_is_asked_by_its_code_in_wgs84() -> None:
    params = boundary_params(
        "au:AdministrativeUnit",
        "au:nationalCode",
        "34150000000",
        {"au": "http://inspire.ec.europa.eu/schemas/au/4.0"},
        "application/geo+json",
    )
    assert (params["REQUEST"], params["SRSNAME"]) == ("GetFeature", "EPSG:4326")
    assert 'xmlns:au="http://inspire.ec.europa.eu/schemas/au/4.0"' in params["FILTER"]
    assert "<fes:Literal>34150000000</fes:Literal>" in params["FILTER"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"<ows:ExceptionReport><ows:ExceptionText>bad</ows:ExceptionText>", "XML, not GeoJSON"),
        (b"{nope", "not JSON"),
        (b'{"type": "Feature"}', "not a GeoJSON FeatureCollection"),
        (b'{"type": "FeatureCollection", "features": []}', "no feature has that code"),
        (b'{"type": "FeatureCollection", "features": [{"properties": {}}]}', "without geometry"),
    ],
)
def test_an_answer_that_is_not_a_boundary_is_refused(content: bytes, message: str) -> None:
    with pytest.raises(BoundaryParseError, match=message):
        parse_boundary(content)


# ── Through the API ──────────────────────────────────────────────────────────────────────

AREA_FIXTURES = {
    "34150000000": "ign_es_nc.json",
    "34090000000": "ign_es_ct.json",
    "ES060": "miteco_es060.json",
    "ES063": "miteco_es063.json",
    "ES064": "miteco_es064.json",
}


def area_fixture(name: str) -> bytes:
    return (FIXTURES / "areas" / name).read_bytes()


def layer_fixture(name: str) -> bytes:
    return (FIXTURES / "layers" / name).read_bytes()


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


class Upstream:
    """Every service behind one MockTransport: boundaries by code, taps by host."""

    def __init__(self, **answers: Any) -> None:
        defaults: dict[str, Any] = {
            "idena.navarra.es": layer_fixture("idena_soils_tafalla.json"),
            "geoserveis.icgc.cat": layer_fixture("icgc_hydrogeology_manresa.xml"),
            "www.juntadeandalucia.es": layer_fixture("rediam_preventive_dalias.gml"),
            "gis.miteco.gob.es": layer_fixture("miteco_at_risk_daimiel.json"),
            "mapas.igme.es": layer_fixture("igme_permeability.xml"),
            "boundaries": None,
        }
        defaults.update(answers)
        self.answers = defaults
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def asked(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host and "FILTER" not in r.url.params]

    def boundaries_asked(self) -> list[httpx.Request]:
        return [r for r in self.requests if "FILTER" in r.url.params]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        if "FILTER" in params:
            override = self.answers["boundaries"]
            if override is not None:
                return (
                    override(request)
                    if callable(override)
                    else httpx.Response(200, content=override)
                )
            code = params["FILTER"].split("<fes:Literal>")[1].split("<")[0]
            return httpx.Response(200, content=area_fixture(AREA_FIXTURES[code]))
        answer = self.answers[request.url.host]
        if callable(answer):
            return answer(request)
        return httpx.Response(200, content=answer)


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


@asynccontextmanager
async def serve(
    settings: Settings, upstream: Upstream, root: Path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, root=root, transport=upstream.transport())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def info(theme: str, lon: float, lat: float, zoom: float = 14) -> str:
    return f"/api/layers/{theme}/info?lon={lon}&lat={lat}&zoom={zoom}"


TAFALLA = (-1.70, 42.55)
MANRESA = (1.80, 41.70)
DALIAS = (-2.80, 36.76)


async def test_an_area_boundary_is_served_rounded_and_read_once(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        first = await client.get("/api/areas/ES-NC")
        second = await client.get("/api/areas/ES-NC")
    assert first.status_code == second.status_code == 200
    body = first.json()
    assert (body["id"], body["kind"], body["grid_deg"]) == ("ES-NC", "region", 0.0001)
    assert body["geometry"]["type"] == "MultiPolygon"
    ring = body["geometry"]["coordinates"][0][0]
    assert ring[0] == ring[-1]
    west, south, east, north = body["bbox"]
    assert -2.51 <= west < east <= -0.72
    assert 41.90 <= south < north <= 43.32
    assert body["source"]["service_id"] == "ign-admin-units"
    assert first.headers["cache-control"] == "public, max-age=2592000"
    (request,) = upstream.requests
    assert request.url.host == "www.ign.es"
    assert request.url.params["TYPENAMES"] == "au:AdministrativeUnit"


async def test_a_boundary_kept_on_disk_is_not_asked_again(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, Upstream(), tmp_path) as client:
        assert (await client.get("/api/areas/ES060")).status_code == 200
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get("/api/areas/ES060")
    assert response.status_code == 200
    assert response.json()["source"]["service_id"] == "miteco-river-basin-districts-wfs"
    assert upstream.requests == []


@pytest.mark.parametrize(
    ("boundaries", "status", "code"),
    [
        (lambda _request: httpx.Response(500), 502, "upstream_error"),
        (_timeout, 504, "upstream_timeout"),
        (b"<ExceptionReport>no</ExceptionReport>", 502, "upstream_error"),
        # A boundary reaching outside its configured box: the configuration is stale.
        (
            json.dumps({"features": [{"geometry": square(5, 5, 6, 6)}]}).encode(),
            502,
            "upstream_error",
        ),
    ],
)
async def test_a_boundary_that_cannot_be_read_is_an_explicit_error(
    settings: Settings, tmp_path: Path, boundaries: Any, status: int, code: str
) -> None:
    async with serve(settings, Upstream(boundaries=boundaries), tmp_path) as client:
        response = await client.get("/api/areas/ES-NC")
    assert response.status_code == status
    assert response.json()["code"] == code
    assert not any((tmp_path / "data" / "cache").rglob("*.bin"))


async def test_an_unknown_area_is_refused_without_calling_out(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get("/api/areas/ES-XX")
    assert response.status_code == 404
    assert response.json()["code"] == "unknown_area"
    assert upstream.requests == []


async def test_a_regional_layer_answers_first_inside_its_area(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("soil-clay", *TAFALLA))
    assert response.status_code == 200
    body = response.json()
    assert body["layer_id"] == "soil-clay"
    assert body["answered_by"] == {
        "level": "regional",
        "layer_id": "navarra-soils",
        "publisher": "Gobierno de Navarra (IDENA)",
        "detail": {"scale_denominator": 25000, "cell_m": None, "edition": 2023},
        "area_id": "ES-NC",
    }
    assert body["fallbacks"] == []
    fields = {f["name"]: f["value"] for f in body["features"][0]["fields"]}
    assert fields["SOILTAXON1"] == "Lithic Xeric Torriorthent"
    # Fields outside the allowlist (the municipality, geometry measures) never leave the API.
    assert "MUNICIPIO" not in response.text
    assert "GEOM_AREA" not in response.text
    assert body["source"]["attribution"] == "Gobierno de Navarra (IDENA), CC BY 4.0"
    (asked,) = upstream.asked("idena.navarra.es")
    assert asked.url.params["QUERY_LAYERS"] == "EDAFOL_Pol_Suelos25m"


async def test_a_proxied_regional_layer_is_read_in_its_own_format(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("groundwater-at-risk", *DALIAS, 12))
    body = response.json()
    assert body["answered_by"]["layer_id"] == "andalusia-preventive-control"
    assert body["answered_by"]["area_id"] == "ES060"
    assert [(f["name"], f["value"]) for f in body["features"][0]["fields"]] == [
        ("thematicIdIdentifier", "ES060MSBT060-013"),
        ("nametext", "CAMPO DE DALÍAS-SIERRA DE GÁDOR"),
        ("control_preventivo", "Sometida a control preventivo"),
    ]
    assert upstream.asked("gis.miteco.gob.es") == []


@pytest.mark.parametrize(
    ("regional", "reason"),
    [
        (layer_fixture("rediam_preventive_empty.gml"), "no_feature"),
        (lambda _request: httpx.Response(503), "upstream_error"),
        (b"<html>maintenance</html>", "upstream_error"),
        (_timeout, "upstream_timeout"),
    ],
)
async def test_the_national_layer_answers_when_the_regional_one_cannot(
    settings: Settings, tmp_path: Path, regional: Any, reason: str
) -> None:
    upstream = Upstream(**{"www.juntadeandalucia.es": regional})
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("groundwater-at-risk", *DALIAS, 12))
    assert response.status_code == 200
    body = response.json()
    assert body["answered_by"]["level"] == "national"
    assert body["answered_by"]["layer_id"] == "groundwater-at-risk"
    assert body["answered_by"]["area_id"] is None
    assert body["answered_by"]["detail"] == {
        "scale_denominator": None,
        "cell_m": None,
        "edition": 2023,
    }
    assert body["fallbacks"] == [{"layer_id": "andalusia-preventive-control", "reason": reason}]
    assert body["features"][0]["fields"][0] == {
        "name": "Código de masa",
        "value": "ES040MSBT000030606",
    }
    assert len(upstream.asked("gis.miteco.gob.es")) == 1


async def test_the_national_layer_answers_when_the_boundary_cannot_be_read(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(boundaries=_timeout)
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("hydrogeology", *MANRESA, 13))
    body = response.json()
    assert body["answered_by"]["layer_id"] == "hydrogeology"
    assert body["fallbacks"] == [
        {"layer_id": "catalonia-hydrogeology", "reason": "boundary_unavailable"}
    ]
    assert upstream.asked("geoserveis.icgc.cat") == []


async def test_a_theme_without_a_national_tap_keeps_the_regional_answer_or_failure(
    settings: Settings, tmp_path: Path
) -> None:
    empty = b'{"type":"FeatureCollection","features":[]}'
    async with serve(settings, Upstream(**{"idena.navarra.es": empty}), tmp_path) as client:
        nothing = await client.get(info("soil-clay", *TAFALLA))
    assert nothing.status_code == 200
    assert nothing.json()["features"] == []
    assert nothing.json()["answered_by"]["layer_id"] == "navarra-soils"
    failing = Upstream(**{"idena.navarra.es": _timeout})
    async with serve(settings, failing, tmp_path / "2") as client:
        failed = await client.get(info("soil-clay", *TAFALLA))
    assert failed.status_code == 504
    assert failed.json()["code"] == "upstream_timeout"


async def test_a_regional_layer_below_its_zoom_is_not_asked(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("soil-clay", *TAFALLA, 10))
    assert response.status_code == 404
    assert response.json()["code"] == "no_feature_info"
    assert upstream.requests == []


async def test_a_point_on_a_border_between_two_areas_asks_one_regional_layer_once(
    settings: Settings, tmp_path: Path
) -> None:
    # The border of the Cuencas Mediterráneas Andaluzas (ES060) and Guadalete y Barbate
    # (ES063), from the same MITECO dataset: a point on an edge both districts share.
    def rings(name: str) -> Any:
        geometry = json.loads(area_fixture(name))["features"][0]["geometry"]
        return round_to_grid(geometry, 0.0001)

    es060, es063 = rings("miteco_es060.json"), rings("miteco_es063.json")
    edges63 = {
        frozenset((ring[i - 1], ring[i]))
        for polygon in es063
        for ring in polygon
        for i in range(len(ring))
    }
    shared = next(
        (ring[i - 1], ring[i])
        for polygon in es060
        for ring in polygon
        for i in range(len(ring))
        if frozenset((ring[i - 1], ring[i])) in edges63
    )
    (x1, y1), (x2, y2) = shared
    point = ((x1 + x2) / 2, (y1 + y2) / 2)
    assert contains(es060, *point) != contains(es063, *point)
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get(info("groundwater-at-risk", *point, 12))
    assert response.json()["answered_by"]["area_id"] in {"ES060", "ES063"}
    assert len(upstream.asked("www.juntadeandalucia.es")) == 1


async def test_a_regional_layer_without_cors_is_drawn_by_the_proxy_from_its_getmap(
    settings: Settings, tmp_path: Path
) -> None:
    png = layer_fixture("igme_lithostrat_export.png")
    upstream = Upstream(**{"www.juntadeandalucia.es": png})
    async with serve(settings, upstream, tmp_path) as client:
        response = await client.get("/api/layers/andalusia-preventive-control/tiles/10/504/404")
    assert response.status_code == 200
    assert response.content == png
    (request,) = upstream.requests
    params = request.url.params
    assert (params["REQUEST"], params["CRS"], params["LAYERS"]) == (
        "GetMap",
        "EPSG:3857",
        "masas_agua_subt_intracom",
    )
    async with serve(settings, Upstream(), tmp_path) as client:
        direct = await client.get("/api/layers/navarra-soils/tiles/10/504/378")
    assert direct.status_code == 404
    assert direct.json()["code"] == "not_proxied"


# One point in every autonomous community and city, at least 2 km from any border. Inside
# Navarra, Catalonia and the Andalusian intra-community districts the regional layer
# answers; everywhere else the national one (or, for soils, nobody: SoilGrids gives no tap).
POINTS = {
    "ES-AN": (-2.80, 36.76),
    "ES-AR": (-0.88, 41.65),
    "ES-AS": (-5.85, 43.36),
    "ES-IB": (2.90, 39.60),
    "ES-CN": (-15.45, 28.10),
    "ES-CB": (-4.05, 43.20),
    "ES-CL": (-4.72, 41.65),
    "ES-CM": (-3.62, 39.07),
    "ES-CT": (1.80, 41.70),
    "ES-VC": (-0.70, 39.25),
    "ES-EX": (-6.35, 38.92),
    "ES-GA": (-7.55, 43.01),
    "ES-MD": (-3.70, 40.42),
    "ES-MC": (-1.70, 37.68),
    "ES-NC": (-1.70, 42.55),
    "ES-PV": (-2.67, 42.85),
    "ES-RI": (-2.45, 42.47),
    "ES-CE": (-5.32, 35.89),
    "ES-ML": (-2.95, 35.29),
}
REGIONAL = {
    "ES-NC": {"soil-clay": "navarra-soils"},
    "ES-CT": {"hydrogeology": "catalonia-hydrogeology"},
    "ES-AN": {"groundwater-at-risk": "andalusia-preventive-control"},
}


@pytest.mark.parametrize("region", sorted(POINTS))
async def test_one_point_per_autonomous_community(
    settings: Settings, tmp_path: Path, region: str
) -> None:
    lon, lat = POINTS[region]
    upstream = Upstream()
    async with serve(settings, upstream, tmp_path) as client:
        for theme in ("soil-clay", "hydrogeology", "groundwater-at-risk"):
            response = await client.get(info(theme, lon, lat, 14))
            expected = REGIONAL.get(region, {}).get(theme)
            if expected is not None:
                assert response.json()["answered_by"]["layer_id"] == expected, theme
                assert response.json()["answered_by"]["level"] == "regional"
            elif theme == "soil-clay":
                assert response.json()["code"] == "no_feature_info"
            else:
                assert response.json()["answered_by"]["layer_id"] == theme
                assert response.json()["fallbacks"] == []
