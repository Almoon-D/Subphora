# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The search settings and the area of interest refuse what cannot be right."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.search import SearchSettings, Territory
from subphora.domain.aoi import AoiOrigin, AreaOfInterest, PointGeometry
from subphora.domain.parcels import LocalPoint, MultiPolygon
from subphora.domain.provenance import Provenance
from subphora.sources.cartociudad import parse_find
from subphora.sources.sigpac import parse_enclosures
from tests.support import copy_config


def _territory(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "t",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "utm_zones": [31],
        "land_check": True,
    }
    entry.update(overrides)
    return entry


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"bbox": [1.0, 0.0, 0.0, 1.0]}, "west, south, east, north"),
        ({"bbox": [0.0, 0.0, 1.0, 95.0]}, "west, south, east, north"),
        ({"land_check": False}, "needs a province"),
        ({"province": "51"}, "names the province"),
    ],
)
def test_a_territory_must_be_consistent(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Territory.model_validate(_territory(**overrides))


def test_territories_must_not_overlap() -> None:
    search = load_settings().search.model_dump()
    search["territories"] = [
        *search["territories"],
        _territory(id="overlap", bbox=[-4.0, 40.0, -3.0, 41.0]),
    ]
    with pytest.raises(ValidationError, match="overlap"):
        SearchSettings.model_validate(search)


def test_the_search_services_must_be_catalogued(tmp_path: Any) -> None:
    config = copy_config(tmp_path)
    (config / "owner.yaml").write_text("search:\n  sigpac:\n    service: nowhere\n")
    with pytest.raises(ValidationError, match="not in the catalogue"):
        load_settings(config)


def test_a_fixed_province_must_exist(tmp_path: Any) -> None:
    from subphora.services.aoi import AoiService

    settings = load_settings()
    territories = list(settings.search.territories)
    territories[-1] = territories[-1].model_copy(update={"province": "99"})
    search = settings.search.model_copy(update={"territories": tuple(territories)})
    with pytest.raises(ValueError, match="no province 99"):
        AoiService(None, settings.model_copy(update={"search": search}), None, None)  # type: ignore[arg-type]


SOURCE = Provenance(
    service_id="s", publisher="p", attribution="a", retrieved_at=datetime(2026, 11, 25, tzinfo=UTC)
)
SQUARE = MultiPolygon(coordinates=((((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),))


def _area(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "origin": AoiOrigin.DRAWN_POINT,
        "label": "0, 0",
        "geometry": PointGeometry(coordinates=(0.0, 0.0)),
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "centre": (0.0, 0.0),
        "centre_local": LocalPoint(crs="EPSG:25831", x=0.0, y=0.0),
        "area_m2": None,
        "municipality": None,
        "province": "P",
        "province_code": "ES-P",
        "region_code": "ES-CL",
        "land_checked": True,
        "sources": (SOURCE,),
    }
    fields.update(overrides)
    return fields


def test_a_valid_point_area() -> None:
    assert AreaOfInterest(**_area()).origin == AoiOrigin.DRAWN_POINT


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"area_m2": 5.0}, "no area"),
        ({"origin": AoiOrigin.DRAWN_POLYGON, "label": None}, "wrong geometry"),
        (
            {"origin": AoiOrigin.CADASTRAL, "geometry": SQUARE, "area_m2": 1.0},
            "only an area found by its cadastral reference",
        ),
        ({"label": None}, "only a drawn polygon"),
        ({"sources": ()}, "names the source"),
    ],
)
def test_an_inconsistent_area_is_refused(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        AreaOfInterest(**_area(**overrides))


def test_a_town_label_without_a_province() -> None:
    body = (
        b'{"type":"poblacion","provinceCode":"13","lat":39.0,"lng":-3.6,"geom":null,'
        b'"address":"Las Casas","muni":"Ciudad Real","poblacion":"Las Casas"}'
    )
    assert parse_find(body, "1").label == "Las Casas"


def test_a_geometry_that_is_not_wkt() -> None:
    body = b'{"type":"Municipio","provinceCode":"13","lat":39.0,"lng":-3.6,"geom":"123"}'
    with pytest.raises(Exception, match="not WKT"):
        parse_find(body, "1")


def test_a_sigpac_ring_that_is_not_a_list() -> None:
    body = (
        b'{"type":"FeatureCollection","crs":{"properties":{"code":"4258"}},"features":[{'
        b'"properties":{"provincia":34,"recinto":1,"superficie":1},'
        b'"geometry":{"type":"Polygon","coordinates":[5]}}]}'
    )
    with pytest.raises(Exception, match="not a list"):
        parse_enclosures(body, "34:1:0:0:1:1:1")
