# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The layer catalogue (config/defaults/map.yaml) and GET /api/map built from it."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from subphora.api.map import MapConfig, map_config
from subphora.config import load_settings
from subphora.domain.parcels import CadastralParcel

ROOT = Path(__file__).resolve().parents[2]


def edit_map(config_dir: Path, change: Any) -> None:
    """Rewrite the map catalogue of a copied config/ with ``change(map_yaml_dict)``."""
    path = config_dir / "defaults" / "map.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def overlay(data: dict[str, Any], layer_id: str) -> dict[str, Any]:
    layers: list[dict[str, Any]] = data["overlays"]["layers"]
    return next(layer for layer in layers if layer["id"] == layer_id)


def test_every_layer_comes_from_the_catalogue() -> None:
    config = map_config(load_settings())
    pnoa, ign, grey = config.base_maps
    assert pnoa.id == "pnoa"  # the default base map
    assert pnoa.tiles[0].startswith("https://www.ign.es/wmts/pnoa-ma?")
    assert pnoa.tiles[0].endswith("tilematrix={z}&tilerow={y}&tilecol={x}")
    assert pnoa.attribution == "PNOA CC-BY 4.0 scne.es"
    assert "layer=IGNBaseTodo" in ign.tiles[0]
    assert "layer=IGNBase-gris" in grey.tiles[0]
    assert ign.attribution == grey.attribution == "IGN Base CC-BY 4.0 scne.es"
    cadastre = config.cadastre
    assert cadastre.url == "https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx"
    assert (cadastre.params["CRS"], cadastre.params["LAYERS"]) == (
        "EPSG:3857",
        "CP.CadastralParcel",
    )
    assert "BBOX" not in cadastre.params
    assert cadastre.min_zoom > config.initial_view.zoom
    assert config.overlay_groups == ("water", "geology", "soil")
    assert {o.group for o in config.overlays} == set(config.overlay_groups)
    assert all(o.attribution for o in config.overlays)


def test_every_layer_covers_all_of_spain() -> None:
    """The same map wherever it is opened (decision 0022): no regional layer."""
    settings = load_settings()
    for overlay in settings.map.overlays.layers:
        service = settings.sources.service(overlay.service)
        assert service.coverage == ["ES"], overlay.id
        assert service.coverage_excludes == [], overlay.id


def test_a_layer_with_cors_and_web_mercator_is_drawn_from_its_service() -> None:
    config = map_config(load_settings())
    status = next(o for o in config.overlays if o.id == "groundwater-status")
    assert not status.proxied
    (tiles,) = status.tiles
    assert tiles.startswith(
        "https://gis.miteco.gob.es/geoserver/agua/estado_masas_aguasub_2027/wms?"
    )
    assert "CRS=EPSG%3A3857" in tiles
    assert tiles.endswith("&BBOX={bbox-epsg-3857}")
    assert status.legend_url is not None
    assert "REQUEST=GetLegendGraphic" in status.legend_url
    assert status.feature_info
    # A base URL with a query of its own keeps it.
    clay = next(o for o in config.overlays if o.id == "soil-clay")
    assert clay.tiles[0].startswith("https://maps.isric.org/mapserv?map=/map/clay.map&SERVICE=WMS")
    assert not clay.feature_info


def test_a_layer_without_cors_or_web_mercator_goes_through_the_proxy() -> None:
    config = map_config(load_settings())
    proxied = {o.id: o for o in config.overlays if o.proxied}
    assert set(proxied) == {"lithostratigraphy"}
    assert proxied["lithostratigraphy"].tiles == (
        "/api/layers/lithostratigraphy/tiles/{z}/{x}/{y}",
    )
    magna = next(o for o in config.overlays if o.id == "magna-lithology")
    assert magna.legend_url is None  # MAGNA's legends are lists of symbol codes


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["base_maps"][0].update(service="nope"), "not in the catalogue"),
        (lambda d: d["base_maps"][0].update(service="catastro-wms"), "not a wmts"),
        (lambda d: d["cadastre"].update(layer="XX"), "does not list layer"),
        (lambda d: d["cadastre"].update(service="rediam-soils", layer="unidades_edaficas"), "CORS"),
        (lambda d: overlay(d, "rivers").update(layer="XX"), "does not list layer"),
        (lambda d: overlay(d, "rivers").update(service="igme-rest"), "not a wms"),
        (lambda d: overlay(d, "lithostratigraphy").pop("export"), "no export"),
        (
            lambda d: overlay(d, "rivers").update(export=overlay(d, "lithostratigraphy")["export"]),
            "has CORS and EPSG:3857; no export is needed",
        ),
        (
            lambda d: overlay(d, "lithostratigraphy")["export"].update(service="igme-magna-wms"),
            "not a rest",
        ),
        (
            lambda d: overlay(d, "lithostratigraphy")["export"].update(service="ideib-groundwater"),
            "export must be on mapas.igme.es",
        ),
        (
            lambda d: overlay(d, "permeability")["legend"].update(url="https://example.org/x.png"),
            "legend must be on mapas.igme.es",
        ),
        (lambda d: overlay(d, "permeability")["legend"].pop("url"), "exactly when its kind"),
        # A service without CORS (REDIAM) cannot be drawn by the browser and has no export.
        (
            lambda d: overlay(d, "rivers").update(
                service="rediam-soils", layer="unidades_edaficas"
            ),
            "lacks CORS or EPSG:3857 and has no export",
        ),
        (lambda d: overlay(d, "rivers").update(group="weather"), "not in groups"),
        (lambda d: overlay(d, "rivers").update(id="springs"), "duplicate overlay ids"),
        (lambda d: overlay(d, "rivers").update(min_zoom=20), "above max_zoom"),
        (lambda d: overlay(d, "rivers")["info"].update(fields=[]), "at least 1"),
        (lambda d: d["overlays"].update(visible_at_start=["nope"]), "unknown overlays"),
        (lambda d: d["base_maps"].append(d["base_maps"][0]), "base map ids must be unique"),
    ],
)
def test_an_undrawable_layer_stops_the_settings(
    config_dir: Path, change: Any, message: str
) -> None:
    edit_map(config_dir, change)
    with pytest.raises(ValueError, match=message):
        load_settings(config_dir)


def test_a_base_map_without_cors_is_refused(config_dir: Path) -> None:
    path = config_dir / "defaults" / "sources.yaml"
    text = path.read_text(encoding="utf-8")
    start = text.index("- id: ign-pnoa-wmts")
    end = text.index("- id: ign-pnoa-wms\n")
    path.write_text(
        text[:start] + text[start:end].replace("cors: true", "cors: false") + text[end:],
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="EPSG:3857 and CORS"):
        load_settings(config_dir)


def test_a_layer_without_web_mercator_needs_a_crs_for_its_taps(config_dir: Path) -> None:
    path = config_dir / "defaults" / "sources.yaml"
    text = path.read_text(encoding="utf-8")
    start = text.index("- id: igme-lithostrat-wms")
    end = text.index("- id: igme-hydrogeo-wms")
    block = text[start:end].replace(
        "crs: [EPSG:4258, EPSG:4326, EPSG:25829, EPSG:25830, EPSG:25831]", "crs: []"
    )
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")
    with pytest.raises(ValueError, match="lists no CRS"):
        load_settings(config_dir)


def test_layers_switched_on_at_start_are_marked_visible(config_dir: Path) -> None:
    edit_map(config_dir, lambda d: d["overlays"].update(visible_at_start=["rivers"]))
    config = map_config(load_settings(config_dir))
    assert [o.id for o in config.overlays if o.visible] == ["rivers"]


def test_the_browser_test_fixtures_match_the_api() -> None:
    """web/e2e/fixtures/ stand in for the API in Playwright: they must keep its shape."""
    fixtures = ROOT / "web" / "e2e" / "fixtures"
    parcel = CadastralParcel.model_validate_json((fixtures / "parcel-santiago.json").read_bytes())
    assert parcel.reference == "7279701NH3477G"
    served = MapConfig.model_validate_json((fixtures / "map.json").read_bytes())
    assert served == map_config(load_settings())
