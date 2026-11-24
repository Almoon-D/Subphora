# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Settings: expert defaults in ``config/defaults/``, owner overrides in ``config/owner.yaml``.

Values live in YAML, mechanics in code. A key the schema does not declare is an error, so a
typo can never be silently ignored.
"""

from pathlib import Path
from typing import Any, Literal

import yaml

from subphora.config.base import Section
from subphora.config.sources import SourcesSettings

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

__all__ = ["CONFIG_DIR", "CoreSettings", "Section", "Settings", "SourcesSettings", "load_settings"]


class CoreSettings(Section):
    """``config/defaults/core.yaml``: replace with the project's first real section."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(Section):
    core: CoreSettings
    sources: SourcesSettings


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
