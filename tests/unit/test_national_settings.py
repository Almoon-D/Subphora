# Copyright (c) 2026 Almoon-D. All rights reserved.
"""model.yaml and national.yaml: what the settings refuse."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from subphora.config import load_settings


def edit(config_dir: Path, name: str, change: Any) -> None:
    path = config_dir / "defaults" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def criterion(data: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    return next(c for c in data["criteria"] if c["id"] == criterion_id)


def refused(config_dir: Path, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        load_settings(config_dir)


def test_the_real_settings_load() -> None:
    settings = load_settings()
    assert sum(c.weight for c in settings.model.criteria if not c.gated) == pytest.approx(1)
    assert [c.id for c in settings.model.gated] == ["vegetation"]
    assert settings.national.grid_of_region("ES-CN").crs == "EPSG:5635"
    assert settings.national.grid_of_region("ES-AN").crs == "EPSG:3035"


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda d: criterion(d, "slope").update(weight=0.5), "add up to 1"),
        (lambda d: criterion(d, "slope").update(variable="index"), "is a result"),
        (lambda d: criterion(d, "slope").update(variable="permeability_class"), "classes lookup"),
        (lambda d: criterion(d, "slope").update(variable="twi"), "same variable"),
        (
            lambda d: criterion(d, "piezometric_depth").update(variable="elevation_m"),
            "lookup exactly",
        ),
        (lambda d: criterion(d, "slope")["lookup"].update(breaks=[5, 2, 10, 20]), "rise"),
        (lambda d: criterion(d, "slope")["lookup"].update(values=[1.0]), "one more value"),
        (lambda d: d["criteria"].append(dict(criterion(d, "slope"))), "unique"),
        (lambda d: d["confidence"]["weights"].update(skill=0.5), "add up to 1"),
        (
            lambda d: criterion(d, "piezometric_depth").update(admission="validated"),
            "needs an input",
        ),
        # A criterion admitted by validation is outside the sum of 1; one always admitted
        # is inside it.
        (lambda d: criterion(d, "vegetation").update(admission="always"), "add up to 1"),
        (lambda d: d["confidence"]["weights"].pop("skill"), "exactly"),
        (lambda d: d["confidence"].update(thresholds={"medium": 0.8, "high": 0.7}), "medium"),
        (lambda d: d["confidence"].update(evidence_none_beyond_m=500), "must exceed"),
        (
            lambda d: d["confidence"]["ageing"].update(geology={"full_years": 9, "zero_years": 9}),
            "zero_years",
        ),
    ],
)
def test_model_settings_refuse(config_dir: Path, change: Any, match: str) -> None:
    edit(config_dir, "model.yaml", change)
    refused(config_dir, match)


def grid(data: dict[str, Any], grid_id: str) -> dict[str, Any]:
    return next(g for g in data["grids"] if g["id"] == grid_id)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda d: grid(d, "canaries").update(regions=[]), "exactly one grid"),
        (lambda d: grid(d, "canaries").update(regions=["canarias"]), "ISO 3166-2"),
        (lambda d: grid(d, "canaries").update(regions=["ES-CN", "ES-CN"]), "one grid only"),
        (lambda d: grid(d, "canaries").update(territories=["ceuta"]), "one grid only"),
        (lambda d: grid(d, "canaries").update(territories=["atlantis"]), "territories"),
        (lambda d: d["grids"].append(dict(grid(d, "canaries"))), "unique"),
        (lambda d: grid(d, "canaries")["terrain"].update(extent=[1, 1, 0, 0]), "extent"),
        (
            lambda d: grid(d, "canaries")["terrain"].update(coverage="Elevacion4083_2"),
            "does not list",
        ),
        (
            lambda d: d["datasets"]["soil"].update(service="ign-mdt-wcs", coverage="x"),
            "does not list",
        ),
        (lambda d: d["datasets"]["terrain"].update(service="igme-rest"), "not a wcs"),
        (lambda d: d["datasets"]["permeability"].update(service="nowhere"), "not in the catalogue"),
        (lambda d: d["datasets"]["water_points"].update(ageing="forever"), "ageing profile"),
        (lambda d: d["datasets"]["groundwater_bodies"].update(srs="EPSG:3035"), "lacks"),
        (lambda d: d["tiles"].update(min_zoom=12), "min_zoom"),
        (lambda d: d["tiles"]["layers"].append(dict(d["tiles"]["layers"][0])), "unique"),
        (lambda d: d["tiles"]["layers"][0].update(colours=["#ffffff"]), "one more colour"),
        (lambda d: d["tiles"]["layers"][0].update(breaks=[0.5, 0.2, 0.6, 0.8]), "rise"),
        (lambda d: d["tiles"]["layers"][0].update(colours=["red"] * 5), "#rrggbb"),
        (lambda d: d["tiles"]["layers"][0].update(variable="groundwater_status"), "categorical"),
        (lambda d: d["datasets"]["vegetation"].update(min_years=9), "min_years"),
        (
            lambda d: d["datasets"]["vegetation"]["season"].update(start="09-15", end="07-15"),
            "ends after",
        ),
        (lambda d: d["datasets"]["vegetation"]["season"].update(start="7-15"), "pattern"),
        (
            lambda d: d["datasets"]["vegetation"]["irrigation"].update(deepest_zoom=12, zoom=13),
            "deepest",
        ),
        (
            lambda d: d["datasets"]["vegetation"].update(pixels_service="earth-search"),
            "not a download",
        ),
        (lambda d: d["datasets"]["vegetation"]["irrigation"].update(service="egms"), "not a rest"),
        (lambda d: d["context"]["ground_motion"].update(service="sigpac-mvt"), "not a download"),
    ],
)
def test_national_settings_refuse(config_dir: Path, change: Any, match: str) -> None:
    edit(config_dir, "national.yaml", change)
    refused(config_dir, match)


def test_the_output_directory_may_be_absolute(config_dir: Path, tmp_path: Path) -> None:
    def absolute(d: dict[str, Any]) -> None:
        d["build"].update(output_dir=str(tmp_path))
        d["context"]["ground_motion"].update(directory=str(tmp_path / "egms"))

    edit(config_dir, "national.yaml", absolute)
    settings = load_settings(config_dir)
    assert settings.national.build.output_path(Path("/elsewhere")) == tmp_path
    assert settings.national.context.ground_motion.path(Path("/elsewhere")) == tmp_path / "egms"
    with pytest.raises(KeyError):
        settings.national.grid("nowhere")
    with pytest.raises(KeyError):
        settings.national.tiles.layer("nowhere")
    with pytest.raises(KeyError):
        settings.model.criterion("nowhere")


def test_the_summers_composited_are_those_already_over() -> None:
    season = load_settings().national.datasets.vegetation.season
    # Mid-July to mid-September: in August the current summer is not over yet.
    assert season.summers(date(2026, 8, 1), 3) == [2023, 2024, 2025]
    assert season.summers(date(2026, 11, 27), 3) == [2024, 2025, 2026]
