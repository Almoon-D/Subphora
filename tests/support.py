# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Shared test helpers: fixtures on disk and a small source catalogue."""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from subphora.config import Settings, load_settings
from subphora.config.sources import SourcesSettings

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ORIGIN = "http://localhost:5173"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / "sources" / name).read_bytes()


def service(**overrides: Any) -> dict[str, Any]:
    """A valid catalogue entry for a WMS on example.org, with overrides."""
    entry: dict[str, Any] = {
        "id": "test-wms",
        "name": "Test WMS",
        "publisher": "Test publisher",
        "kind": "wms",
        "coverage": ["ES"],
        "base_url": "https://wms.example.org/wms",
        "layers": ["CP.CadastralParcel"],
        "crs": ["EPSG:3857"],
        "web_mercator": True,
        "cors": True,
        "licence": "CC BY 4.0",
        "attribution": "Test",
        "terms_url": "https://wms.example.org/terms",
        "knowledge": "docs/knowledge/catastro.md",
        "politeness": {"max_concurrent": 2, "min_interval_s": 0.0, "cache_lifetime_s": 60},
    }
    entry.update(overrides)
    return entry


def catalogue(*services: dict[str, Any], **client: Any) -> SourcesSettings:
    settings: dict[str, Any] = {
        "user_agent": "subphora/{version}",
        "connect_timeout_s": 1,
        "read_timeout_s": 1,
        "retries": 1,
        "retry_backoff_s": 0,
        "max_response_bytes": 100_000,
        "cors_probe_origin": ORIGIN,
    }
    settings.update(client)
    return SourcesSettings.model_validate({"client": settings, "services": list(services)})


def copy_config(tmp_path: Path) -> Path:
    """A copy of the real config/ to edit in a test."""
    target = tmp_path / "config"
    shutil.copytree(ROOT / "config", target)
    return target


def parcel_fixture(name: str) -> bytes:
    return (FIXTURES / "parcels" / name).read_bytes()


def fast_settings(config_dir: Path | None = None) -> Settings:
    """The real configuration with no waiting between requests or retries (tests only)."""
    settings = load_settings(config_dir) if config_dir else load_settings()
    sources = settings.sources
    services = [
        service.model_copy(
            update={"politeness": service.politeness.model_copy(update={"min_interval_s": 0.0})}
        )
        for service in sources.services
    ]
    client = sources.client.model_copy(update={"retry_backoff_s": 0.0})
    return settings.model_copy(
        update={"sources": sources.model_copy(update={"client": client, "services": services})}
    )


type Handler = Callable[[httpx.Request], httpx.Response]


class Catastro:
    """A fake Catastro behind an httpx.MockTransport: canned WFS and DNPRC answers."""

    def __init__(
        self,
        wfs: bytes | Handler = b"",
        dnprc: bytes | Handler = b"",
    ) -> None:
        self.wfs = wfs
        self.dnprc = dnprc
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.wfs if request.url.path.endswith("wfsCP.aspx") else self.dnprc
        if callable(answer):
            return answer(request)
        return httpx.Response(200, content=answer)
