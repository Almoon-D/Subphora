# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The source catalogue's schema refuses an incomplete or inconsistent entry."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.sources import host_of
from tests.support import ROOT, catalogue, service


def test_the_real_catalogue_loads() -> None:
    sources = load_settings().sources
    assert sources.services
    assert "ovc.catastro.meh.es" in sources.allowed_hosts()


def test_every_catalogued_service_has_its_knowledge_file() -> None:
    for entry in load_settings().sources.services:
        path = ROOT / entry.knowledge
        assert path.is_file(), f"{entry.id}: {entry.knowledge} is missing"
        assert entry.host in path.read_text(encoding="utf-8"), (
            f"{entry.id}: {entry.knowledge} does not mention {entry.host}"
        )


def test_no_key_value_lives_in_the_catalogue() -> None:
    text = (ROOT / "config" / "defaults" / "sources.yaml").read_text(encoding="utf-8")
    # Google-style keys start with AIza; JWTs (AEMET) have three base64url parts.
    assert not re.search(r"AIza[0-9A-Za-z_-]{20,}", text)
    assert not re.search(r"eyJ[0-9A-Za-z_-]+\.[0-9A-Za-z_-]+\.", text)


def test_the_foral_territories_are_outside_the_national_cadastre() -> None:
    sources = load_settings().sources
    for entry in sources.services:
        if entry.id.startswith("catastro"):
            assert set(entry.coverage_excludes) == {"ES-NC", "ES-PV"}


def test_an_unknown_id_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        load_settings().sources.service("nope")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"id": "Bad_Id"}, "lower-case"),
        ({"base_url": "http://wms.example.org/wms"}, "https"),
        ({"terms_url": "ftp://example.org"}, "https"),
        ({"knowledge": "notes.txt"}, "docs/knowledge"),
        ({"needs_key": True}, "key_env"),
        ({"key_env": "SOME_KEY"}, "key_env"),
        ({"needs_key": True, "key_env": "lower"}, "environment variable"),
        ({"web_mercator": None}, "web_mercator"),
        ({"kind": "wcs"}, "web_mercator"),
        ({"layers": []}, "layers of interest"),
        ({"kind": "rest", "web_mercator": None}, "sample request"),
        ({"politeness": {"max_concurrent": 0, "min_interval_s": 0, "cache_lifetime_s": 0}}, "0"),
        ({"surprise": 1}, "surprise"),
        ({"coverage": []}, "at least one area"),
        ({"coverage": ["Spain"]}, "ISO 3166"),
        ({"coverage_excludes": ["es-pv"]}, "ISO 3166"),
        ({"coverage": ["ES", "ES-PV"], "coverage_excludes": ["ES-PV"]}, "both covered"),
    ],
)
def test_an_inconsistent_service_is_refused(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        catalogue(service(**overrides))


def test_duplicate_ids_are_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        catalogue(service(), service())


@pytest.mark.parametrize(
    "user_agent", ["subphora/{version} (me@example.org)", "subphora/{version} +https://x", "x"]
)
def test_the_user_agent_is_generic(user_agent: str) -> None:
    with pytest.raises(ValidationError, match="user_agent"):
        catalogue(service(), user_agent=user_agent)


def test_host_of_lowercases_and_requires_https() -> None:
    assert host_of("https://WWW.IGN.es/wmts") == "www.ign.es"
    with pytest.raises(ValueError, match="https"):
        host_of("https:///nohost")


def test_a_broken_catalogue_stops_the_settings(config_dir: Path) -> None:
    path = config_dir / "defaults" / "sources.yaml"
    path.write_text(path.read_text().replace("kind: wmts", "kind: tiles", 1))
    with pytest.raises(ValidationError, match="kind"):
        load_settings(config_dir)
