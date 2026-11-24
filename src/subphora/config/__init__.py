# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Settings: expert defaults in ``config/defaults/``, owner overrides in ``config/owner.yaml``.

Values live in YAML, mechanics in code. A key the schema does not declare is an error, so a
typo can never be silently ignored.
"""

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import model_validator

from subphora.config.base import Section
from subphora.config.map import MapSettings
from subphora.config.server import ApiSettings, StoreSettings
from subphora.config.sources import Service, SourcesSettings

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

__all__ = [
    "CONFIG_DIR",
    "REPO_ROOT",
    "ApiSettings",
    "CoreSettings",
    "MapSettings",
    "Section",
    "Settings",
    "SourcesSettings",
    "StoreSettings",
    "load_settings",
]


class CoreSettings(Section):
    """``config/defaults/core.yaml``: replace with the project's first real section."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(Section):
    core: CoreSettings
    sources: SourcesSettings
    api: ApiSettings
    store: StoreSettings
    map: MapSettings

    @model_validator(mode="after")
    def _map_layers_are_drawable(self) -> Self:
        """Each map layer is a catalogued layer the browser can draw directly (no proxy)."""
        layers = (
            ("map.base", self.map.base.service, self.map.base.layer, "wmts"),
            ("map.cadastre", self.map.cadastre.service, self.map.cadastre.layer, "wms"),
        )
        for key, service_id, layer, kind in layers:
            try:
                service: Service = self.sources.service(service_id)
            except KeyError:
                raise ValueError(f"{key}: {service_id!r} is not in the catalogue") from None
            if service.kind != kind:
                raise ValueError(f"{key}: {service_id} is a {service.kind}, not a {kind}")
            if layer not in service.layers:
                raise ValueError(f"{key}: {service_id} does not list layer {layer!r}")
            if not (service.web_mercator and service.cors):
                raise ValueError(f"{key}: {service_id} needs EPSG:3857 and CORS to be drawn")
        return self


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping")
    return data


def load_settings(config_dir: Path = CONFIG_DIR) -> Settings:
    """Every ``defaults/<section>.yaml`` under its file name, then ``owner.yaml`` on top."""
    raw: dict[str, Any] = {
        path.stem: _read(path) for path in sorted((config_dir / "defaults").glob("*.yaml"))
    }
    owner = config_dir / "owner.yaml"
    if owner.exists():
        raw = _merge(raw, _read(owner))
    return Settings.model_validate(raw)
