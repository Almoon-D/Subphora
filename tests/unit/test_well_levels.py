# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Water levels typed at the well (session 17; decision 0042 buys no instrument): what a
reading states (its reference, who read it, the pump), the batch the device's outbox sends
and every way the registry answers it, the CSV columns for the same, and the owner's
readings at rest as private levels of the depth to water inside their groundwater body,
beside the public piezometry (a reading taken while pumping never enters). Privacy: no
reading in the logs, the report or an unticked export. Every well and place is synthetic."""

import contextlib
import io
import logging
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from subphora.config import Settings
from subphora.domain.wells import (
    LevelReference,
    MeasuredBy,
    PumpState,
    WellReading,
    WellsFailure,
)
from subphora.services.wells_csv import parse_wells_csv
from subphora.store.wells import WellsStore
from tests.national_support import FakeSpain
from tests.parcel_support import parcel_settings, point_area, serve, write_levels
from tests.unit.test_parcel_jobs import analyse
from tests.unit.test_wells import LAT, LON, NAME, body, well


@pytest.fixture
def settings() -> Settings:
    return parcel_settings()


def reading(well_id: str, depth: float = 13.0, **fields: Any) -> WellReading:
    values: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "well_id": well_id,
        "measured_at": datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
        "depth_to_water_m": depth,
        "reference": LevelReference.CASING_TOP,
        "reference_height_m": 0.5,
        "measured_by": MeasuredBy.OWNER,
        "pump": PumpState.STOPPED,
        "pump_minutes": 600,
    }
    return WellReading.model_validate(values | fields)


def batch(*readings: WellReading) -> str:
    return '{"readings": [' + ",".join(r.model_dump_json() for r in readings) + "]}"


# ── What a reading states ──────────────────────────────────────────────────────────────


def test_a_reading_states_its_reference_who_read_it_and_the_pump() -> None:
    w = well()
    r = reading(w.id)
    assert r.below_ground_m == pytest.approx(12.5)
    # The ground stands at no height above itself; an unknown pump has no duration.
    with pytest.raises(ValidationError):
        reading(w.id, reference=LevelReference.GROUND, reference_height_m=0.4)
    with pytest.raises(ValidationError):
        reading(w.id, pump=PumpState.UNKNOWN, pump_minutes=30)
    with pytest.raises(ValidationError):
        reading(w.id, pump_minutes=-1)
    with pytest.raises(ValidationError):
        reading(w.id, reference_height_m=float("inf"))
    # A reading kept before these were asked is from the ground, by someone unknown, with
    # the pump unknown; it compares equal to the same reading with them stated.
    legacy = WellReading.model_validate_json(
        f'{{"id": "{r.id}", "well_id": "{w.id}", "measured_at": "2026-11-20T08:00:00Z",'
        ' "depth_to_water_m": 13.0}'
    )
    assert (legacy.reference, legacy.reference_height_m) == (LevelReference.GROUND, 0.0)
    assert (legacy.measured_by, legacy.pump, legacy.pump_minutes) == (
        MeasuredBy.UNKNOWN,
        PumpState.UNKNOWN,
        None,
    )
    assert legacy.below_ground_m == 13.0


async def test_a_reading_kept_in_the_old_shape_is_the_same_reading_sent_again(
    tmp_path: Path,
) -> None:
    import sqlite3

    store = WellsStore(tmp_path / "wells.sqlite", 1.0)
    w = well()
    await store.put(w)
    r = reading(
        w.id,
        reference=LevelReference.GROUND,
        reference_height_m=0.0,
        measured_by=MeasuredBy.UNKNOWN,
        pump=PumpState.UNKNOWN,
        pump_minutes=None,
    )
    old = (
        f'{{"id":"{r.id}","well_id":"{w.id}",'
        '"measured_at":"2026-11-20T08:00:00Z","depth_to_water_m":13.0}'
    )
    with contextlib.closing(sqlite3.connect(tmp_path / "wells.sqlite")) as db, db:
        db.execute(
            "INSERT INTO readings (id, well_id, measured_at, body, saved_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (r.id, w.id, r.measured_at.isoformat(), old, "2026-11-20T08:00:00+00:00"),
        )
    (result,) = await store.add_readings([r])
    assert result.outcome == "duplicate"
    (record,) = await store.records()
    assert record.readings == (r,)


# ── The outbox's batch ─────────────────────────────────────────────────────────────────


async def test_a_batch_keeps_each_reading_once_and_answers_each_on_its_own(
    settings: Settings, tmp_path: Path
) -> None:
    w = well()
    gone = well(name="Pozo sintético borrado")
    first = reading(w.id)
    later = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    second = reading(w.id, depth=14.0, pump=PumpState.RUNNING, measured_at=later)
    orphan = reading(gone.id)
    async with serve(settings, tmp_path) as client:
        await client.put(f"/api/wells/{w.id}", content=body(w))
        sent = await client.post("/api/wells/readings", content=batch(first, second, orphan))
        # A sync cut by a reload sends the same batch again: nothing is duplicated.
        retried = await client.post("/api/wells/readings", content=batch(first, second))
        other = first.model_copy(update={"depth_to_water_m": 99.0})
        conflict = await client.post("/api/wells/readings", content=batch(other))
        listed = (await client.get("/api/wells")).json()
    assert sent.status_code == 200
    assert [(r["id"], r["outcome"]) for r in sent.json()["results"]] == [
        (first.id, "created"),
        (second.id, "created"),
        (orphan.id, "unknown_well"),
    ]
    assert [r["outcome"] for r in retried.json()["results"]] == ["duplicate", "duplicate"]
    assert [r["outcome"] for r in conflict.json()["results"]] == ["conflict"]
    (record,) = listed["wells"]
    held = record["readings"]
    assert [r["depth_to_water_m"] for r in held] == [13.0, 14.0]
    assert held[0] | {"id": None} == {
        "id": None,
        "well_id": w.id,
        "measured_at": "2026-11-20T08:00:00Z",
        "depth_to_water_m": 13.0,
        "reference": "casing_top",
        "reference_height_m": 0.5,
        "measured_by": "owner",
        "pump": "stopped",
        "pump_minutes": 600,
    }


async def test_a_bad_or_oversized_batch_is_refused_without_echoing_it(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    w = well()
    limit = settings.field.sync.batch_size
    async with serve(settings, tmp_path) as client:
        await client.put(f"/api/wells/{w.id}", content=body(w))
        bad = await client.post(
            "/api/wells/readings",
            content='{"readings": [{"id": "x", "well_id": "y", "depth_to_water_m": 123.456}]}',
        )
        empty = await client.post("/api/wells/readings", content='{"readings": []}')
        many = await client.post(
            "/api/wells/readings", content=batch(*(reading(w.id) for _ in range(limit + 1)))
        )
    assert (bad.status_code, bad.json()["code"]) == (400, WellsFailure.INVALID_WELL)
    assert "123.456" not in bad.text
    assert "123.456" not in caplog.text
    assert empty.status_code == 400
    assert (many.status_code, many.json()["code"]) == (413, WellsFailure.TOO_LARGE)


# ── The CSV columns ────────────────────────────────────────────────────────────────────

DETAILED_CSV = (
    "Nombre;Longitud;Latitud;Fecha medida;Nivel;Referencia;Altura brocal m;Medido por;Bomba;"
    "Minutos bomba\r\n"
    f"{NAME};-3,7001;40,4201;01/03/2025;12,25;Brocal;0,4;Perforista;Parada;180\r\n"
    f"{NAME};-3,7001;40,4201;2025-09-01 08:30;19;;;;En marcha;45\r\n"
    f"{NAME};-3,7001;40,4201;2025-10-01 08:30;14;Suelo;;;;\r\n"
)


def test_a_spreadsheet_states_each_readings_reference_reader_and_pump(
    settings: Settings,
) -> None:
    parsed = parse_wells_csv(DETAILED_CSV.encode("utf-8"), settings.wells)
    casing, pumping, plain = (r for _, r in parsed.readings)
    assert (casing.reference, casing.reference_height_m, casing.below_ground_m) == (
        LevelReference.CASING_TOP,
        0.4,
        pytest.approx(11.85),
    )
    assert (casing.measured_by, casing.pump, casing.pump_minutes) == (
        MeasuredBy.DRILLER,
        PumpState.STOPPED,
        180,
    )
    assert (pumping.reference, pumping.pump, pumping.pump_minutes) == (
        LevelReference.GROUND,
        PumpState.RUNNING,
        45,
    )
    assert (plain.measured_by, plain.pump) == (MeasuredBy.UNKNOWN, PumpState.UNKNOWN)


@pytest.mark.parametrize(
    ("row", "column"),
    [
        (f"{NAME};-3,7;40,4;01/03/2025;12;Azotea;;;;", "reference"),
        (f"{NAME};-3,7;40,4;01/03/2025;12;;;Vecino;;", "measured_by"),
        (f"{NAME};-3,7;40,4;01/03/2025;12;;;;Parada;12,5", "pump_minutes"),
        (f"{NAME};-3,7;40,4;01/03/2025;12;Suelo;0,5;;;", "reading"),
        (f"{NAME};-3,7;40,4;01/03/2025;12;;;;;30", "reading"),
        (f"{NAME};-3,7;40,4;;;;;;Parada;", "reading"),
    ],
)
def test_a_reading_stated_badly_names_its_row_and_column(
    settings: Settings, row: str, column: str
) -> None:
    from subphora.domain.wells import WellsError

    header = DETAILED_CSV.split("\r\n")[0]
    with pytest.raises(WellsError) as caught:
        parse_wells_csv(f"{header}\r\n{row}\r\n".encode(), settings.wells)
    assert caught.value.detail.startswith(f"row 2: {column} ")
    for word in ("Azotea", "Vecino"):
        assert word not in caught.value.detail


# ── The depth to water with the owner's levels ─────────────────────────────────────────


async def explain(client: Any, area_id: str, lon: float = LON, lat: float = LAT) -> Any:
    answer = await client.get(f"/api/parcel/{area_id}/explain", params={"lon": lon, "lat": lat})
    assert answer.status_code == 200
    return answer.json()["depth"]


async def test_a_reading_at_rest_moves_the_depth_at_its_well_and_one_while_pumping_never_does(
    settings: Settings, tmp_path: Path
) -> None:
    write_levels(settings, tmp_path)
    w = well()
    rest = settings.wells.levels.min_rest_minutes
    async with serve(settings, tmp_path, FakeSpain(whole_body=True)) as client:
        _, done = await analyse(client, point_area())
        area_id = done["job"]["id"]
        await client.put(f"/api/wells/{w.id}", content=body(w))
        before = await explain(client, area_id)
        pumping = reading(w.id, depth=2.0, pump=PumpState.RUNNING, pump_minutes=60)
        unknown = reading(w.id, depth=2.0, pump=PumpState.UNKNOWN, pump_minutes=None)
        recovering = reading(w.id, depth=2.0, pump_minutes=rest - 1)
        await client.post("/api/wells/readings", content=batch(pumping, unknown, recovering))
        excluded = await explain(client, area_id)
        at_rest = reading(w.id, depth=13.0)
        await client.post("/api/wells/readings", content=batch(at_rest))
        moved = await explain(client, area_id)
        # 60 m away, inside the same body: the well's level weighs with the piezometers'.
        nearby = await explain(client, area_id, lon=LON + 0.0007)
        analysis = (await client.get(f"/api/parcel/{area_id}")).json()["job"]["analysis"]
    public = before["public"]
    assert public["state"] == "estimated"
    assert public["own_levels"] == []
    # With no reading, both are the public depth.
    assert before["with_wells"] == public
    assert before["left_out"] == {}
    # Pumping, an unknown pump, and a pump stopped too short a while: none enters.
    assert excluded["with_wells"] == public
    assert excluded["left_out"] == {"pumping": 1, "pump_unknown": 1, "recovering": 1}
    # A reading at rest at the well: the depth there is its own, 13 m below a casing top
    # 0.5 m above the ground.
    depth = moved["with_wells"]
    assert depth["state"] == "estimated"
    assert depth["depth_m"] == pytest.approx(12.5)
    assert depth["depth_m"] != pytest.approx(public["depth_m"], abs=1.0)
    (level,) = depth["own_levels"]
    assert level["well_id"] == w.id
    assert level["distance_m"] < 1.0
    assert level["readings"] == 1
    assert (level["first"], level["last"]) == ("2026-11-20", "2026-11-20")
    assert level["ground_m"] - level["level_m"] == pytest.approx(12.5)
    assert depth["water_table"]["piezometers"] == 1
    # Apart from the public piezometry: the public depth is unchanged.
    assert moved["public"] == public
    assert moved["left_out"] == excluded["left_out"]
    # Nearby, the well's level joins the piezometers' and pulls the depth towards its own.
    near = nearby["with_wells"]
    assert near["water_table"]["piezometers"] == nearby["public"]["water_table"]["piezometers"] + 1
    assert [own["well_id"] for own in near["own_levels"]] == [w.id]
    assert near["own_levels"][0]["distance_m"] == pytest.approx(60, abs=10)
    assert abs(near["depth_m"] - 12.5) < abs(nearby["public"]["depth_m"] - 12.5)
    # The area's stored map and its candidates keep the public depth.
    for candidate in analysis["candidates"]:
        assert candidate["depth"]["own_levels"] == []


async def test_a_level_enters_only_inside_its_own_area_and_body_and_stands_without_public_data(
    settings: Settings, tmp_path: Path
) -> None:
    inside = well()
    far = well(name="Pozo sintético lejano", lon=LON + 0.05)
    async with serve(settings, tmp_path, FakeSpain(whole_body=True)) as client:
        _, done = await analyse(client, point_area())
        area_id = done["job"]["id"]
        for w in (inside, far):
            await client.put(f"/api/wells/{w.id}", content=body(w))
        old = reading(inside.id, measured_at=datetime(2001, 1, 1, tzinfo=UTC))
        await client.post("/api/wells/readings", content=batch(reading(far.id), old))
        stale = await explain(client, area_id)
        await client.post("/api/wells/readings", content=batch(reading(inside.id, depth=8.5)))
        fresh = await explain(client, area_id)
    # No public levels were imported: the public depth says so.
    assert stale["public"] == {
        "state": "unknown",
        "reason": "not_imported",
        "ground_m": None,
        "water_table": None,
        "depth_m": None,
        "low_m": None,
        "high_m": None,
        "karst": stale["public"]["karst"],
        "sources": [],
        "own_levels": [],
    }
    # A well outside the detailed map's grid, and readings too old for a level, do not enter.
    assert stale["with_wells"]["reason"] == "not_imported"
    assert stale["left_out"] == {"outside_area": 1, "too_old": 1}
    # The owner's level alone gives the depth at its well, with no public source.
    depth = fresh["with_wells"]
    assert (depth["state"], depth["sources"]) == ("estimated", [])
    assert depth["depth_m"] == pytest.approx(8.0)
    assert depth["own_levels"][0]["first"] == "2026-11-20"
    assert fresh["public"]["reason"] == "not_imported"


def test_a_level_of_another_body_is_never_used(settings: Settings) -> None:
    from subphora.domain.depth import DepthUnknown
    from subphora.model.depth import PiezometerPoint, depth_at

    table = settings.piezometry.water_table
    own_point = PiezometerPoint(
        x=10.0, y=0.0, body="ES099MSBT999", level_m=590.0, low_m=590.0, high_m=590.0, well_id="w"
    )
    from datetime import date

    from subphora.domain.depth import OwnLevel

    own = {
        "w": OwnLevel(
            well_id="w",
            distance_m=0,
            ground_m=600,
            level_m=590,
            low_m=590,
            high_m=590,
            readings=1,
            first=date(2026, 1, 1),
            last=date(2026, 1, 1),
        )
    }
    site = (0.0, 0.0, 600.0)
    alone = depth_at(*site, ("ES030MSBT000", "Body"), [own_point], table, False, None, own)
    inside = depth_at(*site, ("ES099MSBT999", "Other"), [own_point], table, False, None, own)
    assert inside.state == "estimated"
    assert inside.depth_m == pytest.approx(10.0)
    assert [o.distance_m for o in inside.own_levels] == [10.0]
    assert (alone.state, alone.reason) == ("unknown", DepthUnknown.NO_PIEZOMETER_NEARBY)


# ── Privacy ────────────────────────────────────────────────────────────────────────────


async def test_no_reading_reaches_the_logs_the_report_or_an_unticked_export(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    write_levels(settings, tmp_path)
    w = well()
    secret = reading(w.id, depth=17.375)
    async with serve(settings, tmp_path, FakeSpain(whole_body=True)) as client:
        _, done = await analyse(client, point_area())
        area_id = done["job"]["id"]
        caplog.clear()  # the map's own job logs its downloads, not a well
        await client.put(f"/api/wells/{w.id}", content=body(w))
        await client.post("/api/wells/readings", content=batch(secret))
        await client.post(f"/api/wells/{w.id}/readings", content=reading(w.id).model_dump_json())
        await explain(client, area_id)
        plain = await client.get(f"/api/parcel/{area_id}/pack.zip")
        chosen = await client.get(f"/api/parcel/{area_id}/pack.zip", params={"wells": "true"})
        report = await client.get(f"/api/parcel/{area_id}/report.pdf")
    for text in ("17.375", "16.875", secret.id, w.id):
        assert text not in caplog.text
    with zipfile.ZipFile(io.BytesIO(plain.content)) as pack:
        everything = b"".join(pack.read(n) for n in pack.namelist())
    assert secret.id.encode() not in everything
    for figure in (b"17.375", b"16.875"):
        assert figure not in everything
    with zipfile.ZipFile(io.BytesIO(chosen.content)) as pack:
        readings = pack.read("well_readings.csv").decode("utf-8-sig")
    assert readings.splitlines()[0] == (
        "id,well_id,measured_at,depth_to_water_m,reference,reference_height_m,measured_by,"
        "pump,pump_minutes"
    )
    assert (
        f"{secret.id},{w.id},2026-11-20T08:00:00+00:00,17.375,casing_top,0.5,owner,stopped,600"
        in (readings)
    )
    from pypdf import PdfReader

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(report.content)).pages)
    for figure in ("17,4", "16,9", "17.4"):
        assert figure not in text
