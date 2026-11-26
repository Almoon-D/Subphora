# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Offline packs' settings (decision 0037, hard rule 4): only layers whose service's terms
allow storing them can be carried, a service that is never cached can never go offline,
and ``GET /api/map`` tells the browser what a pack holds and what it leaves out, and why."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from subphora.api.map import map_config
from subphora.config import load_settings
from tests.support import catalogue, service


def _edit(config_dir: Path, name: str, change: Callable[[dict[str, Any]], object]) -> None:
    path = config_dir / "defaults" / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _service(data: dict[str, Any], service_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = next(s for s in data["services"] if s["id"] == service_id)
    return entry


def test_a_pack_carries_storable_layers_and_names_every_other_with_its_reason() -> None:
    packs = map_config(load_settings()).packs
    assert [base.id for base in packs.base_maps] == ["pnoa"]
    assert packs.layers == ("potential-index", "potential-confidence")
    excluded = {layer.id: layer for layer in packs.excluded}
    # Catastro forbids tiled requests and massive downloads: never in a pack.
    assert excluded["cadastre"].reason == "forbidden"
    assert excluded["cadastre"].service_id == "catastro-wms"
    # The IGN map may be stored, but packs.yaml does not choose it.
    assert excluded["ign-base"].reason == "not_chosen"
    assert "pnoa" not in excluded
    # Official layers whose terms were not read for this use stay out.
    assert excluded["rivers"].reason == "not_evaluated"
    assert any(layer.kind == "regional" for layer in packs.excluded)
    # The parcel's geometry, from the WFS, may be stored; the cadastral map may not.
    assert "catastro-wfs-parcels" in packs.storable_services
    assert "catastro-wms" not in packs.storable_services


def test_a_service_never_cached_cannot_go_offline() -> None:
    never = {"max_concurrent": 1, "min_interval_s": 0.0, "cache_lifetime_s": 0}
    with pytest.raises(ValueError, match="never cached cannot go offline"):
        catalogue(service(politeness=never, offline="allowed"))
    assert catalogue(service(politeness=never, offline="forbidden")).services[0].offline == (
        "forbidden"
    )
    # Not stated: not evaluated, which counts as forbidden.
    assert catalogue(service()).services[0].offline == "not_evaluated"


@pytest.mark.parametrize(
    ("name", "change", "message"),
    [
        (
            "sources",
            lambda d: _service(d, "ign-pnoa-wmts").update(offline="forbidden"),
            "ign-pnoa-wmts's terms do not allow storing it",
        ),
        (
            "sources",
            lambda d: _service(d, "ign-pnoa-wmts").pop("offline"),
            "ign-pnoa-wmts's terms do not allow storing it",
        ),
        ("packs", lambda d: d["base_maps"].append({"id": "x", "tile_bytes": 1}), "not a map"),
        ("packs", lambda d: d["layers"].append("nope"), "not national tile layers"),
        ("packs", lambda d: d["layers"].append("potential-index"), "listed twice"),
        ("packs", lambda d: d["zoom"].update(min=19, max=18), "min is above max"),
        ("parcel", lambda d: d["layers"].remove("potential-confidence"), "not drawn by"),
    ],
)
def test_a_pack_that_would_store_what_it_may_not_stops_the_settings(
    config_dir: Path, name: str, change: Callable[[dict[str, Any]], object], message: str
) -> None:
    _edit(config_dir, name, change)
    with pytest.raises(ValueError, match=message):
        load_settings(config_dir)
