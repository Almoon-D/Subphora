# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The interpretive cross-section: the apparent-dip arithmetic, contacts with and without
dip data, faults, borehole selection, the "unknown" zone, and the API on the synthetic
Spain (a line through its fault), with every way a line is refused or fails."""

import math
from pathlib import Path
from typing import Any

import httpx
import pytest

from subphora.config import Settings
from subphora.domain.potential import ConfidenceLabel
from subphora.domain.section import (
    Borehole,
    ContactState,
    FaultCrossing,
    SectionGap,
)
from subphora.model.section import (
    BeddingPoint,
    BoreholePoint,
    Line,
    apparent_dip_deg,
    boundary_at,
    columns_of,
    contacts_of,
    place_bedding,
    select_boreholes,
    surface_units,
    unit_at,
)
from tests.national_support import FakeSpain
from tests.parcel_support import parcel_settings, serve, write_levels

# A line 2 km long running east through the synthetic Madrid (its fault at the middle).
WEST, EAST = (-3.7118, 40.42), (-3.6882, 40.42)


@pytest.fixture
def settings() -> Settings:
    return parcel_settings()


# ── Apparent dip ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("dip", "direction", "azimuth", "expected"),
    [
        (30, 90, 90, 30.0),  # the section runs down the dip
        (30, 90, 270, -30.0),  # up the dip: it deepens toward the start
        (30, 90, 0, 0.0),  # along the strike: horizontal
        (30, 90, 45, math.degrees(math.atan(math.tan(math.radians(30)) * math.cos(math.pi / 4)))),
        (0, 123, 77, 0.0),  # a horizontal bed is horizontal whatever the section
        (90, 90, 135, 90.0),  # a vertical bed is vertical
        (90, 90, 300, -90.0),
    ],
)
def test_apparent_dip(dip: float, direction: float, azimuth: float, expected: float) -> None:
    assert apparent_dip_deg(dip, direction, azimuth) == pytest.approx(expected, abs=1e-9)


def test_a_line_places_points_and_finds_crossings() -> None:
    line = Line(0, 0, 1000, 0)
    assert line.azimuth_deg == pytest.approx(90)
    assert Line(0, 0, 0, -10).azimuth_deg == pytest.approx(180)
    assert line.place(300, -40) == pytest.approx((300, 40))  # south of an eastward line: right
    assert line.crossings([(400, -50), (400, 50), (900, 50)]) == pytest.approx([400])
    assert line.crossings([(0, 10), (1000, 10)]) == []  # parallel


# ── Contacts, faults and cells ─────────────────────────────────────────────────────────

_DISTANCES = [float(d) for d in range(0, 1001, 10)]
_GROUNDS: list[float | None] = [500.0] * len(_DISTANCES)


def _units(*runs: tuple[float, str]) -> tuple[list[Any], list[float]]:
    labels = [next(name for end, name in runs if d < end or end == runs[-1][0]) for d in _DISTANCES]
    return surface_units(_DISTANCES, labels, 1000.0)


def test_surface_units_and_their_contacts() -> None:
    units, contacts = _units((300, "A"), (700, "B"), (1000, "C"))
    assert [(u.index, u.label) for u in units] == [(0, "A"), (1, "B"), (2, "C")]
    assert contacts == pytest.approx([295, 695])
    assert units[0].from_m == 0
    assert units[-1].to_m == 1000


def test_a_contact_is_projected_with_the_nearest_measurement(settings: Settings) -> None:
    line = Line(0, 0, 1000, 0)
    units, positions = _units((500, "A"), (1000, "B"))
    bedding = place_bedding(
        line,
        [
            BeddingPoint(520, 30, 30, 90, "Estratificación"),
            BeddingPoint(900, 0, 60, 270, "Estratificación"),
        ],
    )
    [contact] = contacts_of(line, positions, _DISTANCES, _GROUNDS, bedding, [], settings.section)
    assert contact.state is ContactState.PROJECTED
    assert contact.apparent_dip_deg == pytest.approx(30)
    assert contact.measurement is not None
    assert contact.measurement.dip_deg == 30
    # 100 m below the ground the contact lies 100 / tan 30° further along.
    assert boundary_at(contact, 400) == pytest.approx(495 + 100 / math.tan(math.radians(30)))
    # Under the surface of B, near the contact, the cell is still A (the bed dips under B).
    assert unit_at(520, 400, units, [contact], []) == 0
    assert unit_at(800, 400, units, [contact], []) == 1


def test_a_line_with_no_dip_data_draws_vertical_contacts_with_low_confidence(
    settings: Settings,
) -> None:
    line = Line(0, 0, 1000, 0)
    units, positions = _units((500, "A"), (1000, "B"))
    contacts = contacts_of(line, positions, _DISTANCES, _GROUNDS, [], [], settings.section)
    assert [c.state for c in contacts] == [ContactState.NOT_PROJECTED]
    assert contacts[0].apparent_dip_deg is None
    assert boundary_at(contacts[0], 200) == contacts[0].distance_m
    columns = columns_of(
        line,
        _DISTANCES,
        _GROUNDS,
        units,
        contacts,
        [],
        [],
        [],
        settings.section,
        settings.model.confidence,
    )
    interpreted = [c for col in columns for c in col.cells if c.state == "interpreted"]
    assert interpreted
    assert all(c.label is ConfidenceLabel.LOW for c in interpreted)
    assert max(c.confidence or 0 for c in interpreted) <= settings.section.confidence.map_only
    assert all(col.evidence is None and col.evidence_factor == 0 for col in columns)
    # The map alone reaches map_reach_m: below it every cell is unknown.
    reach = settings.section.confidence.map_reach_m
    assert all(c.state == "unknown" for col in columns for c in col.cells if c.top_m >= reach)


def test_a_fault_bounds_the_projection_and_holds_its_contact(settings: Settings) -> None:
    line = Line(0, 0, 1000, 0)
    units, positions = _units((300, "A"), (600, "B"), (1000, "C"))
    faults = [FaultCrossing(distance_m=600, kind="Falla conocida")]
    # A gentle dip toward the end: unbounded, A's contact would run under C.
    bedding = place_bedding(line, [BeddingPoint(300, 0, 10, 90, "Estratificación")])
    contacts = contacts_of(line, positions, _DISTANCES, _GROUNDS, bedding, faults, settings.section)
    assert [c.state for c in contacts] == [ContactState.PROJECTED, ContactState.AT_FAULT]
    assert contacts[1].apparent_dip_deg is None
    # Deep under C, beyond the fault, the cell is C, not A carried across the fault.
    assert boundary_at(contacts[0], 300) > 1000
    assert unit_at(700, 300, units, contacts, faults) == 2
    # Within the first block, A runs under B.
    assert unit_at(550, 300, units, contacts, faults) == 0
    columns = columns_of(
        line,
        _DISTANCES,
        _GROUNDS,
        units,
        contacts,
        faults,
        bedding,
        [],
        settings.section,
        settings.model.confidence,
    )
    at_fault = [
        c for c in columns if abs(c.distance_m - 600) <= settings.section.confidence.fault_zone_m
    ]
    away = [c for c in columns if abs(c.distance_m - 300) < 20]
    assert at_fault
    assert all(c.fault_factor == settings.section.confidence.fault_factor for c in at_fault)
    assert all(c.fault_factor == 1 for c in away)


def test_the_unknown_zone_lies_below_the_deepest_evidence(settings: Settings) -> None:
    line = Line(0, 0, 1000, 0)
    units, _positions = _units(
        (1000, "A"),
    )
    borehole = Borehole(distance_m=100, offset_m=0, kind="Sondeo", depth_m=220, ground_m=500)
    columns = columns_of(
        line,
        _DISTANCES,
        _GROUNDS,
        units,
        [],
        [],
        [],
        [borehole],
        settings.section,
        settings.model.confidence,
    )
    near = min(columns, key=lambda c: abs(c.distance_m - 100))
    assert near.reach_m == 220
    assert near.evidence is not None
    assert near.evidence.value == "borehole"
    assert {c.state for c in near.cells if c.top_m < 220} == {"interpreted"}
    assert {c.state for c in near.cells if c.top_m >= 220} == {"unknown"}
    # Confidence falls with depth.
    values = [c.confidence for c in near.cells if c.confidence is not None]
    assert values == sorted(values, reverse=True)
    # A column with no ground elevation is all unknown.
    holes: list[float | None] = [None] * len(_DISTANCES)
    blind = columns_of(
        line,
        _DISTANCES,
        holes,
        units,
        [],
        [],
        [],
        [borehole],
        settings.section,
        settings.model.confidence,
    )
    assert all(c.state == "unknown" for col in blind for c in col.cells)


def test_boreholes_are_chosen_by_distance_from_the_line(settings: Settings) -> None:
    line = Line(0, 0, 1000, 0)
    limit = settings.section.boreholes.max_distance_m
    points = [
        BoreholePoint(200, limit - 1, "Sondeo", 80, None),  # inside
        BoreholePoint(500, -(limit + 1), "Pozo", 50, 600),  # too far aside
        BoreholePoint(-limit - 1, 0, "Sondeo", 90, None),  # beyond the start
        BoreholePoint(1000 + limit / 2, 0, "Sondeo", 70, None),  # beyond the end, near it
        BoreholePoint(600, 10, "Sondeo", 0, None),  # no depth recorded
    ]
    chosen = select_boreholes(line, points, settings.section)
    assert [(b.distance_m, b.depth_m) for b in chosen] == [(200, 80), (1000 + limit / 2, 70)]
    few = settings.section.model_copy(
        update={"boreholes": settings.section.boreholes.model_copy(update={"max_count": 1})}
    )
    assert [b.distance_m for b in select_boreholes(line, points, few)] == [1000 + limit / 2]


# ── The API ────────────────────────────────────────────────────────────────────────────


async def _section(client: httpx.AsyncClient, start: Any, end: Any) -> httpx.Response:
    return await client.post("/api/section", json={"start": list(start), "end": list(end)})


async def test_a_line_through_the_fault_gets_its_section(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await _section(client, WEST, EAST)
    assert answer.status_code == 200
    body = answer.json()
    assert body["label"] == "interpretation"
    assert body["crs"] == "EPSG:25830"
    assert body["length_m"] == pytest.approx(2000, rel=0.01)
    assert [u["label"] for u in body["units"]] == ["Calizas", "Margas", "Areniscas"]
    first, second = body["contacts"]
    assert first["state"] == "projected"
    # Bedding 20° toward the east, cut by a line running (nearly) east.
    assert first["apparent_dip_deg"] == pytest.approx(20, abs=0.5)
    assert second["state"] == "at_fault"
    [fault] = body["faults"]
    assert fault["distance_m"] == pytest.approx(1000, abs=10)
    [borehole] = body["boreholes"]
    assert borehole["depth_m"] == 120
    # The inventory's 0 is a blank: the terrain's elevation stands in.
    assert borehole["ground_m"] is not None
    assert borehole["ground_m"] > 0
    assert [m["kind"] for m in body["bedding"]] == ["Estratificación"]
    assert set(body["gaps"]) == {SectionGap.NO_BOREHOLE_LOGS, SectionGap.NO_WATER_TABLE}
    assert {p["reason"] for p in body["water_table"]} == {"not_imported"}
    assert set(body["sources"]) == {
        "terrain",
        "lithology",
        "faults",
        "bedding",
        "boreholes",
        "groundwater_bodies",
    }
    cells = [c for col in body["columns"] for c in col["cells"]]
    assert {c["state"] for c in cells} == {"interpreted", "unknown"}
    assert all(c["confidence"] is not None for c in cells if c["state"] == "interpreted")


async def test_the_water_table_comes_from_the_imported_levels(
    settings: Settings, tmp_path: Path
) -> None:
    write_levels(settings, tmp_path)
    async with serve(settings, tmp_path) as client:
        body = (await _section(client, WEST, EAST)).json()
    states = {p["state"] for p in body["water_table"]}
    assert states == {"estimated", "unknown"}  # the body covers the west half only
    west = body["water_table"][0]
    assert west["water_table"]["body"] == "ES030MSBT000"
    assert [s["service_id"] for s in body["levels"]] == ["miteco-piezometry-db"]
    assert SectionGap.NO_WATER_TABLE not in body["gaps"]


async def test_a_line_without_map_or_dip_says_so(settings: Settings, tmp_path: Path) -> None:
    spain = FakeSpain(bedding=False, lithology=False)
    async with serve(settings, tmp_path, spain) as client:
        body = (await _section(client, WEST, EAST)).json()
    assert body["units"] == []
    assert body["contacts"] == []
    assert {SectionGap.NO_UNITS, SectionGap.NO_BEDDING} <= set(body["gaps"])
    assert all(c["state"] == "unknown" for col in body["columns"] for c in col["cells"])


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        ((-3.70, 40.42), (-3.6995, 40.42), "too_short"),
        ((-3.80, 40.42), (-3.60, 40.42), "too_long"),
        ((-3.70, 40.42), (-15.5, 28.1), "outside_territory"),
        ((2.0, 50.0), (2.01, 50.0), "outside_territory"),
    ],
)
async def test_a_line_is_refused(
    settings: Settings, tmp_path: Path, start: Any, end: Any, code: str
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await _section(client, start, end)
    assert answer.status_code == 422
    assert answer.json()["code"] == code


async def test_a_malformed_line_is_refused(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        bad = await client.post("/api/section", json={"start": [1, 2]})
        degrees = await _section(client, (500, 40), (-3.7, 40.42))
    assert bad.status_code == 400
    assert bad.json()["code"] == "invalid_line"
    assert degrees.status_code == 400


async def test_a_line_outside_the_terrain_coverage_is_refused(
    settings: Settings, tmp_path: Path
) -> None:
    coverage = settings.parcel.terrain.coverages["mainland"].model_copy(
        update={"extent": (0.0, 0.0, 10.0, 10.0)}
    )
    terrain = settings.parcel.terrain.model_copy(
        update={"coverages": {**settings.parcel.terrain.coverages, "mainland": coverage}}
    )
    narrow = settings.model_copy(
        update={"parcel": settings.parcel.model_copy(update={"terrain": terrain})}
    )
    async with serve(narrow, tmp_path) as client:
        answer = await _section(client, WEST, EAST)
    assert answer.status_code == 422
    assert answer.json()["code"] == "outside_coverage"


@pytest.mark.parametrize(("fail", "status"), [({"mapas.igme.es": 500}, 502)])
async def test_a_failed_download_fails_the_section(
    settings: Settings, tmp_path: Path, fail: dict[str, int], status: int
) -> None:
    async with serve(settings, tmp_path, FakeSpain(fail=fail)) as client:
        answer = await _section(client, WEST, EAST)
    assert answer.status_code == status
    assert answer.json()["code"] == "upstream_error"


async def test_a_slow_service_times_the_section_out(settings: Settings, tmp_path: Path) -> None:
    spain = FakeSpain(timeout=frozenset({"servicios.idee.es"}))
    async with serve(settings, tmp_path, spain) as client:
        answer = await _section(client, WEST, EAST)
    assert answer.status_code == 504
    assert answer.json()["code"] == "upstream_timeout"
