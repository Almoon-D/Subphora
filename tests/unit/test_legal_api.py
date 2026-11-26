# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal filter through the API (``GET /api/legal``): the layers it asks, what it makes
of them, and what it says when they cannot be read; and the settings that refuse rules
reading layers or fields the map does not have."""

import json
import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from subphora.config import REPO_ROOT, Settings, load_settings
from tests.support import fast_settings
from tests.unit.test_regional_layers import DAIMIEL, DALIAS, Upstream, serve


def _status(code: str, name: str, status: str) -> bytes:
    """A tap on MITECO's status layer, by the aliases its answer gives (synthetic values
    in the recorded shape of docs/knowledge/miteco-basins.md)."""
    feature = {
        "type": "Feature",
        "geometry": None,
        "properties": {
            "Cód. Masa de agua": code,
            "Nombre masa de agua": name,
            "Estado cuantitativo": status,
        },
    }
    return json.dumps({"type": "FeatureCollection", "features": [feature]}).encode()


EMPTY = json.dumps({"type": "FeatureCollection", "features": []}).encode()
MANCHA = _status("ES040MSBT000030606", "Mancha Occidental I", "Malo")


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


def legal(lon: float, lat: float, region: str) -> str:
    return f"/api/legal?lon={lon}&lat={lat}&region={region}"


async def test_a_closed_perimeter_of_the_guadiana_is_probably_not_allowed(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(estado_masas_aguasub_2027=MANCHA, DPH_Estimado=EMPTY)
    async with serve(settings, upstream, tmp_path) as client:
        answer = await client.get(legal(*DAIMIEL, "ES-CM"))
    assert answer.status_code == 200
    body = answer.json()
    assert body["state"] == "probably_not_allowed"
    assert body["authority"]["name"] == "Confederación Hidrográfica del Guadiana"
    assert body["body"] == {
        "code": "ES040MSBT000030606",
        "name": "Mancha Occidental I",
        "quantitative_status": "Malo",
        "declared_at_risk": True,
        "declaration": (
            "Anuncio de la Confederación Hidrográfica del Guadiana sobre Declaración de la Masa"
            " de Agua Subterránea Mancha Occidental I en riesgo de no alcanzar el buen estado"
            " cuantitativo y químico"
        ),
    }
    findings = {f["rule_id"]: f for f in body["findings"]}
    assert findings["phgn-11-1-perimeters"]["outcome"] == "blocks"
    assert findings["phgn-11-1-perimeters"]["values"] == {"zone": "Laguna de las Yeguas"}
    assert findings["rdph-84-2-at-risk"]["outcome"] == "authorisation"
    # No distances at an area's centre: measured per candidate.
    assert findings["phgn-23-2-distance"]["message"] == "distance_not_measured"
    assert findings["rdph-87-2-distance"]["message"] == "superseded"
    assert body["not_loaded"] == []
    assert body["disclaimer"].startswith("Guidance, not legal advice")
    # Only the layers of the rules that apply here were asked; Andalusia's was not.
    assert not upstream.asked("www.juntadeandalucia.es")


async def test_preventive_control_in_an_andalusian_district(
    settings: Settings, tmp_path: Path
) -> None:
    status = _status("ES060MSBT060-013", "Campo de Dalías-Sierra de Gádor", "Malo")
    upstream = Upstream(estado_masas_aguasub_2027=status, DPH_Estimado=EMPTY)
    async with serve(settings, upstream, tmp_path) as client:
        body = (await client.get(legal(*DALIAS, "ES-AN"))).json()
    assert body["authority"]["level"] == "regional"
    assert body["state"] == "conditions_apply"
    assert body["not_loaded"] == []
    findings = {f["rule_id"]: f for f in body["findings"]}
    assert findings["phcma-39-preventive"]["outcome"] == "authorisation"
    # The at-risk layer answers another body there: this one is not declared.
    assert body["body"]["declared_at_risk"] is False


async def test_unreadable_layers_leave_rules_unchecked_never_passed(
    settings: Settings, tmp_path: Path
) -> None:
    upstream = Upstream(**{"gis.miteco.gob.es": lambda _r: httpx.Response(500, content=b"x")})
    async with serve(settings, upstream, tmp_path) as client:
        answer = await client.get(legal(*DAIMIEL, "ES-CM"))
    assert answer.status_code == 200
    body = answer.json()
    assert body["state"] == "rules_not_loaded"
    assert body["authority"] is None
    assert body["body"] is None
    assert body["not_loaded"][0]["scope"] == "district"
    assert "could not be read" in body["not_loaded"][0]["reason"]["en"]
    findings = {f["rule_id"]: f for f in body["findings"]}
    assert findings["rdph-84-2-at-risk"]["outcome"] == "check"
    assert findings["rdph-87-4-policia"]["outcome"] == "check"


@pytest.mark.parametrize("region", ["andalusia", "ES-an", "ES"])
async def test_the_region_is_an_iso_code(settings: Settings, tmp_path: Path, region: str) -> None:
    async with serve(settings, Upstream(), tmp_path) as client:
        answer = await client.get(legal(*DAIMIEL, region))
    assert answer.status_code == 422


# ── The rules as data refuse what cannot be evaluated ────────────────────────────────


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "config" / "defaults", tmp_path / "defaults")
    shutil.copytree(REPO_ROOT / "config" / "legal", tmp_path / "legal")
    return tmp_path


def _edit(path: Path, change: Any) -> None:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(content)
    path.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")


@pytest.mark.parametrize(
    ("file", "change", "message"),
    [
        ("es.yaml", lambda d: d["rules"][0].update(area="ES-AN"), "is not keyed ES"),
        (
            "es040.yaml",
            lambda d: d["rules"][0]["match"].update(layer="no-such-layer"),
            "not a map or regional layer",
        ),
        (
            "es020.yaml",
            lambda d: d["rules"][0]["match"].update(field="titular"),
            "does not keep 'titular'",
        ),
        (
            "es050.yaml",
            lambda d: d["rules"][2].update(supersedes=["nothing"]),
            "supersedes unknown",
        ),
        (
            "es-an.yaml",
            lambda d: d["rules"][1].update(where={"districts": ["ES999"]}),
            "unknown districts",
        ),
        (
            "es.yaml",
            lambda d: d["rules"].append(dict(d["rules"][0])),
            "unique",
        ),
        (
            "areas.yaml",
            lambda d: d["districts"]["ES050"].update(plan={"state": "partial"}),
            "says why",
        ),
        (
            "es050.yaml",
            lambda d: d["rules"][2]["cases"][0].update(curve=[[3000, 500], [1000, 50]]),
            "rises in volume",
        ),
        (
            "es060.yaml",
            lambda d: d["rules"][2]["cases"][0].update(none_set=True),
            "once",
        ),
        ("es.yaml", lambda d: d.update(rules={}), "a list under 'rules'"),
    ],
)
def test_a_rule_that_cannot_be_evaluated_stops_the_settings(
    config_dir: Path, file: str, change: Any, message: str
) -> None:
    _edit(config_dir / "legal" / "es" / file, change)
    with pytest.raises(ValueError, match=message):
        load_settings(config_dir)


def test_a_rule_without_a_trigger_is_refused(config_dir: Path) -> None:
    def strip(d: dict[str, Any]) -> None:
        d["rules"][2]["declared_at_risk"] = False

    _edit(config_dir / "legal" / "es" / "es.yaml", strip)
    with pytest.raises(ValueError, match="names no body status"):
        load_settings(config_dir)
