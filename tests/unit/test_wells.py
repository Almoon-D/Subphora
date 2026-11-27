# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The owner's well registry and learning from it (MASTER_PLAN §4.3 Learning, §3 Privacy;
decision 0040): the update on synthetic wells (one productive, one dry), its range
limits, the CSV import, the registry's API and every way it refuses, the detailed map's
"updated with your wells" layer, the validation against the owner's wells, and privacy
(no registry data in logs or exports unless chosen). Every well and place is synthetic."""

import csv
import io
import logging
import math
import uuid
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from subphora.__main__ import main
from subphora.config import Settings
from subphora.config.wells import UpdateSettings
from subphora.domain.validation import MEASURED, LabelDesign
from subphora.domain.wells import Well, WellOutcome, WellReading, WellsError, WellsFailure
from subphora.model.learning import KnownWell, update_at, update_grid, weight
from subphora.services.wells_csv import parse_wells_csv, stable_id
from tests.national_support import FakeSpain
from tests.parcel_support import parcel_settings, point_area, serve
from tests.unit.test_parcel_jobs import analyse

# The synthetic centre of a point area near Madrid, and a well's made-up name.
LON, LAT = -3.70, 40.42
NAME = "Pozo sintético Zarzaluz"


@pytest.fixture
def settings() -> Settings:
    return parcel_settings()


def update_settings(**changes: Any) -> UpdateSettings:
    return parcel_settings().wells.update.model_copy(update=changes)


def well(
    outcome: WellOutcome = WellOutcome.PRODUCTIVE,
    lon: float = LON,
    lat: float = LAT,
    name: str = NAME,
    **fields: Any,
) -> Well:
    return Well(
        id=fields.pop("id", str(uuid.uuid4())),
        name=name,
        longitude=lon,
        latitude=lat,
        outcome=outcome,
        **fields,
    )


def known(outcome: WellOutcome, x: float = 0.0, y: float = 0.0) -> KnownWell:
    return KnownWell(id=str(uuid.uuid4()), outcome=outcome, x=x, y=y)  # type: ignore[arg-type]


# ── The update ─────────────────────────────────────────────────────────────────────────


def test_a_well_weighs_one_at_itself_half_at_the_half_distance_and_nothing_beyond_range() -> None:
    s = update_settings(half_weight_m=100.0, range_m=400.0)
    w = weight(np.array([0.0, 100.0, 200.0, 400.0, 400.1, 5000.0]), s)
    assert w.tolist() == pytest.approx([1.0, 0.5, 0.25, 0.0625, 0.0, 0.0])


def test_one_productive_well_raises_its_neighbourhood_and_one_dry_lowers_it() -> None:
    s = update_settings(prior_strength=2.0, half_weight_m=100.0, range_m=400.0)
    prior = 0.4
    up = update_at(prior, "index", 0.0, 0.0, [known(WellOutcome.PRODUCTIVE)], s)
    down = update_at(prior, "index", 0.0, 0.0, [known(WellOutcome.DRY)], s)
    # (n p + 1) / (n + 1) at the well itself, and (n p) / (n + 1) at a dry one.
    assert up.value == pytest.approx((2 * 0.4 + 1) / 3)
    assert down.value == pytest.approx((2 * 0.4) / 3)
    assert up.low <= up.value <= up.high
    assert down.low <= down.value <= down.high
    assert up.kind == "index"
    assert up.prior == prior
    (evidence,) = up.evidence
    assert (evidence.outcome, evidence.distance_m, evidence.weight) == ("productive", 0, 1)
    # Both together balance out towards a half; farther wells weigh less.
    both = update_at(
        prior, "index", 0.0, 0.0, [known(WellOutcome.PRODUCTIVE), known(WellOutcome.DRY)], s
    )
    assert both.value == pytest.approx((2 * 0.4 + 1) / 4)
    farther = update_at(prior, "index", 0.0, 0.0, [known(WellOutcome.PRODUCTIVE, x=100.0)], s)
    assert prior < farther.value < up.value
    assert farther.evidence[0].weight == pytest.approx(0.5)


def test_beyond_its_range_a_well_changes_nothing_and_the_value_is_the_maps_own() -> None:
    s = update_settings(half_weight_m=100.0, range_m=400.0)
    far = update_at(0.37, "probability", 0.0, 0.0, [known(WellOutcome.DRY, x=400.5)], s)
    assert far.evidence == ()
    assert far.value == 0.37
    assert far.kind == "probability"
    # A prior at the very edge is kept off 0 and 1, so one well still moves it.
    edge = update_at(0.0, "index", 0.0, 0.0, [known(WellOutcome.PRODUCTIVE)], s)
    assert edge.value > 0.3


def test_the_grid_update_is_local_bounded_and_leaves_empty_cells_empty() -> None:
    s = update_settings(prior_strength=2.0, half_weight_m=50.0, range_m=200.0)
    prior = np.full((100, 100), 0.5, dtype=np.float32)
    prior[0, 0] = np.nan
    # A 10 m grid from (0, 1000): the productive well at the centre of cell (20, 20), the
    # dry one at the centre of cell (80, 80).
    wells = [known(WellOutcome.PRODUCTIVE, 205.0, 795.0), known(WellOutcome.DRY, 805.0, 195.0)]
    updated = update_grid(prior, 0.0, 1000.0, 10.0, wells, s)
    assert updated[20, 20] == pytest.approx((2 * 0.5 + 1) / 3)
    assert updated[80, 80] == pytest.approx((2 * 0.5) / 3)
    assert updated[20, 24] < updated[20, 20]  # 40 m away weighs less
    # 210 m from the well (beyond the range) and everywhere far from both: unchanged.
    assert updated[20, 41] == 0.5
    assert updated[50, 50] == 0.5
    assert math.isnan(updated[0, 0])
    finite = updated[~np.isnan(updated)]
    assert finite.min() > 0
    assert finite.max() < 1
    # The point update agrees with the grid's at a cell centre.
    at = update_at(0.5, "index", 245.0, 795.0, wells, s)
    assert at.value == pytest.approx(float(updated[20, 24]), abs=1e-6)


def test_the_update_settings_refuse_a_range_below_the_half_distance() -> None:
    with pytest.raises(ValidationError, match="range_m"):
        UpdateSettings.model_validate(
            {**update_settings().model_dump(), "half_weight_m": 500.0, "range_m": 100.0}
        )


def test_the_wells_layer_needs_an_index_legend_and_its_own_id(settings: Settings) -> None:
    raw = settings.model_dump()
    for change, message in (
        ({"legend_layer": "potential-confidence"}, "legend_layer"),
        ({"layer_id": "potential-index"}, "layer_id"),
    ):
        wells = {**raw["wells"], "update": {**raw["wells"]["update"], **change}}
        with pytest.raises(ValidationError, match=message):
            Settings.model_validate({**raw, "wells": wells})


def test_a_well_and_a_reading_check_what_they_hold() -> None:
    with pytest.raises(ValidationError):
        well(id="not-a-uuid")
    with pytest.raises(ValidationError):
        well(name=" padded ")
    with pytest.raises(ValidationError):
        well(flow_l_s=-1.0)
    from datetime import datetime

    with pytest.raises(ValidationError):
        WellReading(
            id=str(uuid.uuid4()),
            well_id=str(uuid.uuid4()),
            measured_at=datetime(2026, 1, 1),  # no time zone
            depth_to_water_m=10.0,
        )


# ── CSV import ─────────────────────────────────────────────────────────────────────────

SPANISH_CSV = (
    "Nombre;Longitud;Latitud;Profundidad;Caudal;Resultado;Fecha medida;Nivel\r\n"
    f"{NAME};-3,7001;40,4201;85,5;2,5;Productivo;01/03/2025;12,25\r\n"
    f"{NAME};-3,7001;40,4201;;;;2025-09-01 08:30;14,5\r\n"
    "Sondeo sintético Seco;-3,6995;40,4195;120;0;;;\r\n"
    "Pozo sin probar;-3,6990;40,4190;;;;;\r\n"
)


def test_a_spanish_spreadsheet_is_read_with_its_readings_outcomes_and_decimal_commas(
    settings: Settings,
) -> None:
    parsed = parse_wells_csv(SPANISH_CSV.encode("cp1252"), settings.wells)
    assert parsed.rows == 4
    wells = {w.name: w for _, w in parsed.wells}
    assert len(wells) == 3
    first = wells[NAME]
    assert (first.longitude, first.latitude) == (-3.7001, 40.4201)
    assert (first.depth_m, first.flow_l_s, first.outcome) == (85.5, 2.5, WellOutcome.PRODUCTIVE)
    assert first.id == stable_id("well", "pozo_sintetico_zarzaluz")
    # A blank outcome is read from the flow: 0 is dry, none is unknown.
    assert wells["Sondeo sintético Seco"].outcome is WellOutcome.DRY
    assert wells["Pozo sin probar"].outcome is WellOutcome.UNKNOWN
    readings = [r for _, r in parsed.readings]
    assert [r.depth_to_water_m for r in readings] == [12.25, 14.5]
    # Local time (Madrid) as UTC: winter +1, summer +2.
    assert [r.measured_at.isoformat() for r in readings] == [
        "2025-02-28T23:00:00+00:00",
        "2025-09-01T06:30:00+00:00",
    ]


def test_a_position_in_utm_is_read_with_its_crs(settings: Settings) -> None:
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True).transform(LON, LAT)
    content = f"name,x,y,crs,outcome\n{NAME},{x:.2f},{y:.2f},25830,dry\n".encode()
    ((_, read),) = parse_wells_csv(content, settings.wells).wells
    assert (read.longitude, read.latitude) == pytest.approx((LON, LAT), abs=1e-6)
    assert read.outcome is WellOutcome.DRY


@pytest.mark.parametrize(
    ("content", "failure", "detail"),
    [
        ("nombre,profundidad\nA,10\n", WellsFailure.INVALID_CSV, "no position columns"),
        ("lon,lat\n1,2\n", WellsFailure.INVALID_CSV, "no column for the well's name"),
        ("", WellsFailure.INVALID_CSV, "empty"),
        (
            f"name,lon,lat\n{NAME},abc,40\n",
            WellsFailure.INVALID_CSV,
            "row 2: longitude is not a number",
        ),
        (
            f"name,lon,lat,outcome\n{NAME},-3,40,quizás\n",
            WellsFailure.INVALID_CSV,
            "row 2: outcome",
        ),
        (
            f"name,lon,lat,depth_m\n{NAME},-3,40,10\n{NAME},-3,40,11\n",
            WellsFailure.INVALID_CSV,
            "row 3: depth_m differs from row 2",
        ),
        (
            f"name,lon,lat,fecha\n{NAME},-3,40,2025-01-01\n",
            WellsFailure.INVALID_CSV,
            "row 2: reading",
        ),
        (
            f"name,lon,lat,fecha,nivel\n{NAME},-3,40,ayer,3\n",
            WellsFailure.INVALID_CSV,
            "row 2: measured_at",
        ),
        (f"name,x,y,crs\n{NAME},1,2,utm\n", WellsFailure.INVALID_CSV, "row 2: crs"),
        (
            f"name,lon,lat\n{NAME},-300,40\n",
            WellsFailure.INVALID_CSV,
            "row 2: longitude is not valid",
        ),
    ],
)
def test_a_bad_file_names_the_row_and_column_never_the_value(
    settings: Settings, content: str, failure: WellsFailure, detail: str
) -> None:
    with pytest.raises(WellsError) as caught:
        parse_wells_csv(content.encode(), settings.wells)
    assert caught.value.failure is failure
    assert detail in caught.value.detail
    assert NAME not in caught.value.detail
    assert "quizás" not in caught.value.detail


def test_a_file_too_large_or_too_long_is_refused(settings: Settings) -> None:
    csv_settings = settings.wells.csv.model_copy(update={"max_bytes": 10, "max_rows": 1})
    small = settings.wells.model_copy(update={"csv": csv_settings})
    with pytest.raises(WellsError, match="at most 10 bytes"):
        parse_wells_csv(b"name,lon,lat\n" + b"x" * 20, small)
    rows = settings.wells.model_copy(
        update={"csv": settings.wells.csv.model_copy(update={"max_rows": 1})}
    )
    with pytest.raises(WellsError, match="at most 1 rows"):
        parse_wells_csv(b"name,lon,lat\nA,-3,40\nB,-3,40\n", rows)


# ── The registry's API ─────────────────────────────────────────────────────────────────


def body(w: Well) -> str:
    return w.model_dump_json()


async def test_the_registry_stores_replaces_and_deletes_wells_and_keeps_each_reading_once(
    settings: Settings, tmp_path: Path
) -> None:
    w = well(depth_m=60.0)
    async with serve(settings, tmp_path) as client:
        created = await client.put(f"/api/wells/{w.id}", content=body(w))
        again = await client.put(f"/api/wells/{w.id}", content=body(w))
        changed = w.model_copy(update={"outcome": WellOutcome.DRY})
        replaced = await client.put(f"/api/wells/{w.id}", content=body(changed))
        reading = WellReading(
            id=str(uuid.uuid4()),
            well_id=w.id,
            measured_at="2026-06-01T08:00:00Z",  # type: ignore[arg-type]
            depth_to_water_m=21.5,
        )
        path = f"/api/wells/{w.id}/readings"
        first = await client.post(path, content=reading.model_dump_json())
        retried = await client.post(path, content=reading.model_dump_json())
        other = reading.model_copy(update={"depth_to_water_m": 30.0})
        conflict = await client.post(path, content=other.model_dump_json())
        listed = await client.get("/api/wells")
        deleted = await client.delete(f"/api/wells/{w.id}")
        gone = await client.delete(f"/api/wells/{w.id}")
        orphan = await client.post(path, content=reading.model_dump_json())
        empty = await client.get("/api/wells")
    assert (created.status_code, created.json()["change"]) == (201, "created")
    assert (again.status_code, again.json()["change"]) == (200, "unchanged")
    assert replaced.json()["change"] == "updated"
    assert (first.status_code, retried.json()["change"]) == (201, "unchanged")
    assert (conflict.status_code, conflict.json()["code"]) == (409, "conflict")
    (record,) = listed.json()["wells"]
    assert record["well"]["outcome"] == "dry"
    assert [r["depth_to_water_m"] for r in record["readings"]] == [21.5]
    assert listed.headers["cache-control"] == "no-store"
    assert (deleted.status_code, gone.status_code) == (204, 404)
    assert orphan.status_code == 404
    assert empty.json()["wells"] == []
    # The stamp moves with the wells that update the map.
    assert empty.json()["stamp"] != listed.json()["stamp"]


async def test_the_registry_refuses_bad_records_without_echoing_them(
    settings: Settings, tmp_path: Path
) -> None:
    w = well()
    long_name = well(name="N" * (settings.wells.name_max_chars + 1))
    async with serve(settings, tmp_path) as client:
        mismatch = await client.put(f"/api/wells/{uuid.uuid4()}", content=body(w))
        malformed = await client.put(
            f"/api/wells/{w.id}", content=body(w).replace(str(LAT), '"norte"')
        )
        too_long = await client.put(f"/api/wells/{long_name.id}", content=body(long_name))
        bad_address = await client.put("/api/wells/not-a-uuid", content=body(w))
        wrong_well = await client.post(
            f"/api/wells/{uuid.uuid4()}/readings",
            content=WellReading(
                id=str(uuid.uuid4()),
                well_id=w.id,
                measured_at="2026-06-01T08:00:00Z",  # type: ignore[arg-type]
                depth_to_water_m=1.0,
            ).model_dump_json(),
        )
    assert (mismatch.status_code, mismatch.json()["code"]) == (400, "invalid_well")
    assert malformed.status_code == 400
    assert malformed.json()["detail"] == "the well is not valid at latitude"
    assert too_long.status_code == 400
    assert bad_address.status_code == 422
    assert wrong_well.status_code == 400
    for answer in (mismatch, malformed, too_long, wrong_well):
        assert NAME not in answer.text


async def test_an_import_is_idempotent_and_reports_rows_that_disagree(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        first = await client.post("/api/wells/import", content=SPANISH_CSV.encode())
        second = await client.post("/api/wells/import", content=SPANISH_CSV.encode())
        edited = SPANISH_CSV.replace(";14,5", ";15,0").replace(";120;0;", ";130;0;")
        third = await client.post("/api/wells/import", content=edited.encode())
        broken = await client.post("/api/wells/import", content=b"lon,lat\n1,2\n")
        listed = (await client.get("/api/wells")).json()
    assert first.status_code == 200
    report = first.json()
    assert report["rows"] == 4
    assert report["wells"]["created"] == 3
    assert report["readings"]["created"] == 2
    again = second.json()
    assert again["wells"]["unchanged"] == 3
    assert again["readings"]["unchanged"] == 2
    assert again["conflict_rows"] == []
    # The edited level and depth are conflicts; the registry keeps what it held.
    assert third.json()["conflict_rows"] == [3, 4]
    assert (broken.status_code, broken.json()["code"]) == (422, "invalid_csv")
    held = {r["well"]["name"]: r for r in listed["wells"]}
    assert held["Sondeo sintético Seco"]["well"]["depth_m"] == 120
    assert [r["depth_to_water_m"] for r in held[NAME]["readings"]] == [12.25, 14.5]


async def test_a_failing_registry_says_so(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "data" / "wells"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("a file where the registry's folder goes")
    async with serve(settings, tmp_path) as client:
        answer = await client.get("/api/wells")
    assert (answer.status_code, answer.json()["code"]) == (503, "store_unavailable")
    assert "the well registry failed" in caplog.text


# ── The detailed map updated with the wells ────────────────────────────────────────────


async def test_a_logged_well_changes_the_nearby_values_visibly_in_the_updated_layer(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        _, done = await analyse(client, point_area())
        area_id = done["job"]["id"]
        layers = {layer["id"]: layer for layer in done["layers"]}
        wells_layer = layers[settings.wells.update.layer_id]
        index_image = (await client.get(layers["potential-index"]["image"])).content
        before = await client.get(wells_layer["image"])
        tap = {"lon": LON, "lat": LAT}
        plain = (await client.get(f"/api/parcel/{area_id}/explain", params=tap)).json()
        productive = well(WellOutcome.PRODUCTIVE)
        await client.put(f"/api/wells/{productive.id}", content=body(productive))
        raised = (await client.get(f"/api/parcel/{area_id}/explain", params=tap)).json()
        after_answer = (await client.get(f"/api/parcel/{area_id}")).json()
        new_layer = next(lyr for lyr in after_answer["layers"] if lyr["id"] == wells_layer["id"])
        after = await client.get(new_layer["image"])
        dry = well(WellOutcome.DRY, lon=LON + 0.0002)
        await client.put(f"/api/wells/{dry.id}", content=body(dry))
        balanced = (await client.get(f"/api/parcel/{area_id}/explain", params=tap)).json()
        await client.put(
            f"/api/wells/{productive.id}",
            content=body(productive.model_copy(update={"outcome": WellOutcome.DRY})),
        )
        lowered = (await client.get(f"/api/parcel/{area_id}/explain", params=tap)).json()
    assert wells_layer["visible"] is False
    assert wells_layer["legend"] == layers["potential-index"]["legend"]
    # With no well the updated layer is the index layer itself, and the tap says so.
    assert before.headers["cache-control"] == "no-store"
    assert before.content == index_image
    assert plain["updated"]["evidence"] == []
    assert plain["updated"]["value"] == plain["estimate"]["score"]
    # One productive well raises the value next to it, visibly in the layer.
    update = raised["updated"]
    assert update["kind"] == "index"
    assert update["prior"] == pytest.approx(plain["estimate"]["score"])
    assert update["value"] > update["prior"] + 0.05
    (evidence,) = update["evidence"]
    assert evidence["well_id"] == productive.id
    assert evidence["distance_m"] < settings.parcel.resolution_m
    assert new_layer["image"] != wells_layer["image"]  # its address carries the new stamp
    assert after.content != index_image
    # The tapped estimate itself is the map's own, unchanged.
    assert raised["estimate"] == plain["estimate"]
    # A dry well beside it pulls it back; two dry ones lower it well below the map's value.
    assert balanced["updated"]["value"] < update["value"]
    assert len(balanced["updated"]["evidence"]) == 2
    assert lowered["updated"]["value"] < plain["estimate"]["score"] - 0.1


async def test_the_updated_layer_of_an_unknown_or_unfinished_map_is_refused(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await client.get(f"/api/parcel/{'0' * 16}/layers/potential-wells")
    assert answer.status_code == 404


# ── The index against the owner's wells ────────────────────────────────────────────────


async def test_the_owners_wells_are_validated_apart_productive_against_dry(
    settings: Settings, tmp_path: Path
) -> None:
    from tests.unit.test_national_build import build

    await build(settings, tmp_path, FakeSpain(), "-3.80,40.30,-3.55,40.55")
    spots = [(-3.78 + 0.05 * i, 40.32 + 0.045 * j) for i in range(5) for j in range(5)]
    records = [
        well(WellOutcome.PRODUCTIVE if i % 2 else WellOutcome.DRY, lon, lat, f"W{i}")
        for i, (lon, lat) in enumerate(spots)
    ]
    off_map = well(WellOutcome.PRODUCTIVE, lon=-6.0, lat=37.5)
    untested = well(WellOutcome.UNKNOWN)
    async with serve(settings, tmp_path) as client:
        for w in [*records, off_map, untested]:
            assert (await client.put(f"/api/wells/{w.id}", content=body(w))).status_code == 201
        few = (await client.get("/api/wells/validation")).json()
    domains = {v["domain"]: v for v in few["validations"]}
    assert set(domains) == {"ES030MSBT000", "none"}
    assert sum(v["productive"] + v["dry"] for v in domains.values()) == len(records)
    for domain in domains.values():
        assert domain["design"] == LabelDesign.PRESENCE_ABSENCE
        assert domain["state"] == "not_enough_labels"
        assert domain["background"] == 0
        assert domain["labels_source"] == settings.wells.validation.labels_source
        assert domain["excluded_criteria"] == []
    assert (few["off_map"], few["unknown_outcome"]) == (1, 1)
    # With thresholds the owner's handful reaches, the same wells are measured.
    validation = settings.validation
    lowered = settings.model_copy(
        update={
            "validation": validation.model_copy(
                update={
                    "minimum": validation.minimum.model_copy(
                        update={"productive": 3, "dry": 3, "blocks": 2}
                    ),
                    "calibration": validation.calibration.model_copy(
                        update={"min_per_class": 3, "folds": 2}
                    ),
                }
            )
        }
    )
    async with serve(lowered, tmp_path) as client:
        measured = (await client.get("/api/wells/validation")).json()
    domain = next(v for v in measured["validations"] if v["domain"] == "ES030MSBT000")
    assert domain["state"] in {s.value for s in MEASURED}
    assert domain["auc"] is not None


async def test_without_a_national_map_every_known_well_is_off_the_map(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        w = well()
        await client.put(f"/api/wells/{w.id}", content=body(w))
        answer = (await client.get("/api/wells/validation")).json()
    assert answer == {"validations": [], "off_map": 1, "unknown_outcome": 0}


# ── Privacy ────────────────────────────────────────────────────────────────────────────


async def test_no_registry_data_reaches_the_logs_or_an_export_unless_chosen(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    w = well(note="Nota privada sintética")
    async with serve(settings, tmp_path) as client:
        _, done = await analyse(client, point_area())
        area_id = done["job"]["id"]
        caplog.clear()  # the map's own job logs its downloads, not a well
        await client.put(f"/api/wells/{w.id}", content=body(w))
        await client.post("/api/wells/import", content=SPANISH_CSV.encode())
        await client.get(f"/api/parcel/{area_id}/explain", params={"lon": LON, "lat": LAT})
        await client.get(f"/api/parcel/{area_id}/layers/potential-wells")
        await client.get("/api/wells/validation")
        plain = await client.get(f"/api/parcel/{area_id}/pack.zip")
        chosen = await client.get(f"/api/parcel/{area_id}/pack.zip", params={"wells": "true"})
        report = await client.get(f"/api/parcel/{area_id}/report.pdf")
    for secret in (NAME, "Nota privada", f"{LON}", f"{LAT}", w.id):
        assert secret not in caplog.text
    with zipfile.ZipFile(io.BytesIO(plain.content)) as pack:
        names = pack.namelist()
        assert "wells.csv" not in names
        assert "well_readings.csv" not in names
        everything = b"".join(pack.read(n) for n in names)
        manifest = pack.read("manifest.json").decode()
    assert NAME.encode() not in everything
    assert "wells_left_out" in manifest
    with zipfile.ZipFile(io.BytesIO(chosen.content)) as pack:
        rows = list(csv.DictReader(io.StringIO(pack.read("wells.csv").decode("utf-8-sig"))))
        readings = pack.read("well_readings.csv").decode("utf-8-sig")
        assert "wells_left_out" not in pack.read("manifest.json").decode()
    assert {r["name"] for r in rows} >= {NAME}
    assert "12.25" in readings
    from pypdf import PdfReader

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(report.content)).pages)
    assert NAME not in text


def test_the_command_line_imports_counts_and_validates_without_printing_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import subphora.config

    monkeypatch.setattr(subphora.config, "REPO_ROOT", tmp_path)
    file = tmp_path / "pozos.csv"
    file.write_bytes(SPANISH_CSV.encode("utf-8"))
    assert main(["wells", "import", str(file)]) == 0
    assert main(["wells", "import", str(file)]) == 0
    assert main(["wells", "summary"]) == 0
    assert main(["wells", "validate"]) == 0
    assert main(["wells", "import", str(tmp_path / "missing.csv")]) == 1
    out = capsys.readouterr().out
    assert "4 rows: wells 3 created; readings 2 created" in out
    assert "4 rows: wells 3 unchanged; readings 2 unchanged" in out
    assert "3 wells (1 dry, 1 productive, 1 unknown); 2 readings" in out
    assert "not on the national map: 2; outcome unknown: 1" in out
    assert "FAILED" in out
    assert NAME not in out
    assert (tmp_path / "data" / "wells" / "wells.sqlite").exists()


def test_store_failures_are_errors_of_the_registry(settings: Settings, tmp_path: Path) -> None:
    import asyncio

    from subphora.services.wells import WellsService
    from subphora.store.wells import WellsStore

    (tmp_path / "wells.sqlite").mkdir()
    store = WellsStore(tmp_path / "wells.sqlite", 0.1)
    with pytest.raises(WellsError) as caught:
        asyncio.run(store.records())
    assert caught.value.failure is WellsFailure.STORE_UNAVAILABLE
    # The detailed map still answers: the registry's stamp says it is unavailable.
    (tmp_path / "data").write_text("a file where data/ goes")
    stamp = asyncio.run(WellsService(settings, tmp_path).current_stamp())
    assert len(stamp) == 16
