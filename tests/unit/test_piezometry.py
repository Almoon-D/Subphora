# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Importing the national piezometry database (MASTER_PLAN §4.3, depth): an Access file
read by mdb-export (a stand-in script here, printing excerpts of the real tables), the
summary per piezometer, the UTM zone of each row, and every way the import fails."""

import shutil
import stat
import sys
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from subphora.__main__ import main
from subphora.config import Settings, load_settings
from subphora.config.depth import ChjBasin, GuadianaBasin
from subphora.domain.piezometry import Piezometer, PiezometryDataset
from subphora.services.basin_levels import read_basin
from subphora.services.piezometry import import_piezometry, piezometer_points, summarise
from subphora.sources.piezometry import (
    PiezometryReadError,
    access_file,
    export_table,
    workbook_rows,
)
from subphora.store.piezometry import read_piezometry
from tests.unit.test_depth import SOURCE

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "piezometry"
BASINS = FIXTURES / "basins"
NATIONAL, JUCAR, GUADIANA = "miteco-piezometry-db", "chj-piezometry", "chguadiana-piezometry"
NOW = datetime(2026, 11, 26, tzinfo=UTC)

# Prints the fixture CSV of the table named last on its command line, like mdb-export;
# checks that the dates are asked as ISO dates and the database exists.
_FAKE = """\
import sys
from pathlib import Path
args = sys.argv[1:]
assert args[:4] == ["-D", "%Y-%m-%d", "-T", "%Y-%m-%d"], args
assert Path(args[4]).is_file(), args[4]
if args[5] == "missing":
    print("Error: table missing", file=sys.stderr)
    sys.exit(1)
sys.stdout.write((Path({folder!r}) / (args[5] + ".csv")).read_text(encoding="utf-8"))
"""


@pytest.fixture
def fake_mdb_export(tmp_path: Path) -> str:
    script = tmp_path / "mdb-export"
    script.write_text(f"#!{sys.executable}\n" + _FAKE.format(folder=str(FIXTURES)))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def database(tmp_path: Path, zipped: bool = True) -> Path:
    access = tmp_path / "Piezo.accdb"
    access.write_bytes(b"Standard ACE DB")
    if not zipped:
        return access
    archive = tmp_path / "basedatospiezometria.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(access, "Piezo.accdb")
    return archive


def settings_for(
    path: Path, mdb_export: str, tmp_path: Path, basins: Path | None = None, **summary: float
) -> Settings:
    """The default settings on the fixture database; the basin files are read from
    ``basins`` (a folder), or are absent."""
    settings = load_settings()
    folder = basins or tmp_path / "no-basins"
    piezometry = settings.piezometry.model_copy(
        update={
            "input": path,
            "output": tmp_path / "out" / "piezometers.json",
            "mdb_export": mdb_export,
            "summary": settings.piezometry.summary.model_copy(update=summary),
            "basins": [
                b.model_copy(update={"input": folder / b.input.name})
                for b in settings.piezometry.basins
            ],
        }
    )
    return settings.model_copy(update={"piezometry": piezometry})


def test_the_import_summarises_each_piezometer_with_recent_levels(
    tmp_path: Path, fake_mdb_export: str
) -> None:
    settings = settings_for(database(tmp_path), fake_mdb_export, tmp_path)
    dataset = import_piezometry(settings, tmp_path, NOW)
    assert dataset.piezometers_read == 6
    assert dataset.levels_read == 111
    # Left out: the removed one (last level before 2008) and the one with no body.
    assert dataset.left_out == 2
    by_id = {p.id: p for p in dataset.piezometers}
    assert set(by_id) == {"1549", "1550", "6438", "4040"}
    porches = by_id["1549"]
    assert porches.name == "Los Porches"
    assert porches.body == "ES040MSBT000030607"
    assert porches.body_label == "Sierra de Altomira"
    assert porches.ground_m == 703.67
    assert porches.level_low_m <= porches.level_m <= porches.level_high_m
    assert porches.last.year == 2024
    # Zone 30, in Cuenca; zone 31 (despite the column name), in Catalonia.
    assert -2.8 < porches.longitude < -2.7
    assert 39.4 < porches.latitude < 39.5
    assert by_id["6438"].longitude > 0.5
    (source,) = dataset.sources
    assert len(source.sha256) == 64
    assert source.service_id == "miteco-piezometry-db"
    assert source.file_name == "basedatospiezometria.zip"
    assert source.levels_to == max(p.last for p in dataset.piezometers)
    assert all(p.sources == ("miteco-piezometry-db",) for p in dataset.piezometers)
    assert read_piezometry(tmp_path / "out" / "piezometers.json") == dataset


def test_an_access_file_can_be_read_without_a_zip(tmp_path: Path, fake_mdb_export: str) -> None:
    rows = list(export_table(database(tmp_path, zipped=False), "01_Piezometros", fake_mdb_export))
    assert [r["IDPIEZ"] for r in rows] == ["1549", "1550", "6438", "1591", "5705", "4040"]


def test_a_level_is_the_recent_median_and_too_few_or_too_old_are_left_out() -> None:
    settings = load_settings().piezometry
    levels = [(date(2024, month, 1), float(month)) for month in range(1, 13)]
    summary = summarise(levels, settings.summary, date(2026, 11, 26))
    assert summary is not None
    assert summary.level == pytest.approx(6.5)
    assert summary.low < summary.level < summary.high
    assert summary.count == 12
    # Only the recent window counts: a level 20 years before the last is not in it.
    with_old = summarise([(date(2004, 1, 1), 999.0), *levels], settings.summary, date(2026, 11, 26))
    assert with_old is not None
    assert with_old.count == 12
    assert summarise(levels[:3], settings.summary, date(2026, 11, 26)) is None
    assert summarise(levels, settings.summary, date(2045, 1, 1)) is None
    assert summarise([], settings.summary, date(2026, 11, 26)) is None


def _point() -> Piezometer:
    return Piezometer(
        id="1",
        code="a",
        name="",
        body="B",
        body_label="",
        longitude=-3.70,
        latitude=40.42,
        ground_m=None,
        level_m=600,
        level_low_m=599,
        level_high_m=601,
        measurements=5,
        first=date(2024, 1, 1),
        last=date(2024, 6, 1),
        sources=(SOURCE.service_id,),
    )


def test_piezometers_are_projected_and_kept_only_near_the_area() -> None:
    near = _point()
    far = near.model_copy(update={"id": "2", "longitude": -3.0})
    dataset = PiezometryDataset(
        sources=(SOURCE,),
        piezometers_read=2,
        levels_read=10,
        left_out=0,
        piezometers=(near, far),
    )
    (point,) = piezometer_points(
        dataset, "EPSG:25830", (439_000, 4_473_000, 441_000, 4_476_000), 5000
    )
    assert point.body == "B"
    assert point.x == pytest.approx(440_250, abs=500)


def test_a_missing_or_wrong_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PiezometryReadError, match="does not exist"), access_file(tmp_path / "x"):
        pass
    text = tmp_path / "x.txt"
    text.write_text("x")
    with pytest.raises(PiezometryReadError, match="neither an Access"), access_file(text):
        pass


def test_a_zip_without_one_database_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("readme.txt", "x")
    with pytest.raises(PiezometryReadError, match="one Access database"), access_file(archive):
        pass


def test_without_mdbtools_or_with_a_failing_export_the_import_says_why(
    tmp_path: Path, fake_mdb_export: str
) -> None:
    access = database(tmp_path, zipped=False)
    with pytest.raises(PiezometryReadError, match="install mdbtools"):
        list(export_table(access, "01_Piezometros", str(tmp_path / "no-such-command")))
    with pytest.raises(PiezometryReadError, match="table missing"):
        list(export_table(access, "missing", fake_mdb_export))


def test_an_import_that_keeps_nothing_fails(tmp_path: Path, fake_mdb_export: str) -> None:
    settings = settings_for(database(tmp_path), fake_mdb_export, tmp_path, min_measurements=999)
    with pytest.raises(ValueError, match="no piezometer"):
        import_piezometry(settings, tmp_path, NOW)


def test_an_unreadable_import_asks_for_a_new_one(tmp_path: Path) -> None:
    path = tmp_path / "piezometers.json"
    assert read_piezometry(path) is None
    path.write_text("{}")
    with pytest.raises(ValueError, match="import` again"):
        read_piezometry(path)


def test_the_command_imports_and_reports(
    tmp_path: Path,
    fake_mdb_export: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = tmp_path / "config"
    (owner / "defaults").mkdir(parents=True)
    for path in (Path(__file__).resolve().parents[2] / "config" / "defaults").glob("*.yaml"):
        (owner / "defaults" / path.name).write_text(path.read_text(encoding="utf-8"))
    shutil.copytree(Path(__file__).resolve().parents[2] / "config" / "legal", owner / "legal")
    output = tmp_path / "levels.json"
    (owner / "owner.yaml").write_text(
        f"piezometry:\n  mdb_export: {fake_mdb_export}\n  output: {output}\n  basins: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("subphora.__main__.load_settings", lambda: load_settings(owner))
    assert main(["piezometry", "import", "--file", str(database(tmp_path))]) == 0
    printed = capsys.readouterr().out
    assert "4 piezometers kept of 6 (2 left out)" in printed
    assert output.exists()
    assert main(["piezometry", "import", "--file", str(tmp_path / "absent.zip")]) == 1
    assert "FAILED" in capsys.readouterr().out


# ── Basin spreadsheets ─────────────────────────────────────────────────────────────────


def _basin[T: (ChjBasin, GuadianaBasin)](kind: type[T], **update: object) -> T:
    (basin,) = (b for b in load_settings().piezometry.basins if isinstance(b, kind))
    return basin.model_copy(update={"input": BASINS / basin.input.name, **update})


def test_basin_levels_join_the_national_piezometers_by_code(
    tmp_path: Path, fake_mdb_export: str
) -> None:
    settings = settings_for(database(tmp_path), fake_mdb_export, tmp_path, basins=BASINS)
    dataset = import_piezometry(settings, tmp_path, NOW)
    assert [s.service_id for s in dataset.sources] == [NATIONAL, JUCAR, GUADIANA]
    by_id = {p.id: p for p in dataset.piezometers}
    # Los Porches (04.01.017): the national levels end in 2024, Guadiana's run to 2026.
    porches = by_id["1549"]
    assert porches.sources == (NATIONAL, GUADIANA)
    assert porches.last.year == 2026
    national = dataset.source_map()[NATIONAL]
    assert national.levels_to.year == 2024
    assert dataset.source_map()[GUADIANA].levels_to == date(2026, 10, 1)
    # Only in Guadiana's file: its body name ("BULLAQUE") is the national one's.
    retuerta = by_id[f"{GUADIANA}:04.07.208"]
    assert (retuerta.body, retuerta.sources) == ("ES040MSBT000030601", (GUADIANA,))
    assert retuerta.last == date(2026, 10, 1)
    # Only in Júcar's file: its own body code, prefixed.
    albarracin = by_id[f"{JUCAR}:08.01.002"]
    assert (albarracin.body, albarracin.sources) == ("ES080MSBT080-114", (JUCAR,))
    assert 40.4 < albarracin.latitude < 40.5
    # Left out: Rus-Valdelobos (a body no national piezometer here names) and a Júcar
    # point with no body and no level.
    assert f"{GUADIANA}:04.01.013" not in by_id
    assert all(p.code != "08.29.057" for p in dataset.piezometers)
    assert dataset.piezometers_read == 6 + 2 + 3
    assert dataset.left_out == dataset.piezometers_read - len(dataset.piezometers)
    assert read_piezometry(tmp_path / "out" / "piezometers.json") == dataset


def test_a_guadiana_depth_becomes_a_level_below_its_ground() -> None:
    found = read_basin(_basin(GuadianaBasin), BASINS / "Red Oficial Guadiana OCTUBRE 2026.xlsx")
    station = found.stations["04.01.017"]
    assert station.ground_m == 703.67
    assert station.body is None
    assert station.body_label == "SIERRA DE ALTOMIRA"
    levels = dict(found.levels["04.01.017"])
    rows = list(workbook_rows(BASINS / "Red Oficial Guadiana OCTUBRE 2026.xlsx"))
    header, row = rows[1], next(r for r in rows if r[2] == "04.01.017")
    column = header.index(next(h for h in header if getattr(h, "year", 0) == 2022))
    assert levels[date(2022, 1, 1)] == pytest.approx(703.67 - float(row[column]))  # type: ignore[arg-type]
    assert found.rows_read > 0


def test_jucar_static_levels_are_read_across_its_workbooks() -> None:
    found = read_basin(_basin(ChjBasin), BASINS / "F71_Puntos_de_control_piezometrico.zip")
    assert set(found.stations) == {"08.01.002", "08.02.001", "08.29.057"}
    assert found.stations["08.29.057"].body is None
    # The months alternate between the two workbooks; both are read.
    assert found.rows_read == 126
    # Two rows hold only a dynamic level (read while pumping): skipped.
    assert len(found.levels["08.01.002"]) + len(found.levels["08.02.001"]) == 124


def test_a_missing_basin_file_is_skipped_and_the_import_says_so(
    tmp_path: Path,
    fake_mdb_export: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for(database(tmp_path), fake_mdb_export, tmp_path)
    dataset = import_piezometry(settings, tmp_path, NOW)
    assert [s.service_id for s in dataset.sources] == [NATIONAL]
    monkeypatch.setattr("subphora.__main__.load_settings", lambda: settings)
    assert main(["piezometry", "import"]) == 0
    printed = capsys.readouterr().out
    assert f"{JUCAR}: not imported" in printed
    assert f"{NATIONAL} (basedatospiezometria.zip): 4 piezometers" in printed


@pytest.mark.parametrize(
    ("basin", "match"),
    [
        (lambda: _basin(GuadianaBasin, levels_sheet="Otra"), "no sheet 'Otra'"),
        (
            lambda: _basin(
                GuadianaBasin,
                columns=_basin(GuadianaBasin).columns.model_copy(update={"ground": "Cota"}),
            ),
            r"lacks the columns \['Cota'\]",
        ),
        (lambda: _basin(GuadianaBasin, header_row=1), r"lacks the columns \['CÓDIGO"),
        (lambda: _basin(ChjBasin, levels_members="Niveles_*.xlsx"), "holds no"),
        (lambda: _basin(ChjBasin, stations_member="Otro.xlsx"), "not a readable"),
    ],
)
def test_a_basin_file_not_as_configured_is_refused(basin: object, match: str) -> None:
    settings = basin()  # type: ignore[operator]
    with pytest.raises(PiezometryReadError, match=match):
        read_basin(settings, settings.input)


def test_a_file_that_is_no_workbook_is_refused(tmp_path: Path) -> None:
    text = tmp_path / "x.xlsx"
    text.write_text("x")
    with pytest.raises(PiezometryReadError, match="not a readable"):
        list(workbook_rows(text))
    with pytest.raises(PiezometryReadError, match="does not exist"):
        list(workbook_rows(tmp_path / "absent.xlsx"))
    with pytest.raises(PiezometryReadError, match="not a zip"):
        read_basin(_basin(ChjBasin), text)


def test_body_codes_are_written_as_the_bodies_layer_writes_them() -> None:
    piezometry = load_settings().piezometry
    assert piezometry.body_code("ES080MSBT080.115") == "ES080MSBT080-115"
    assert piezometry.body_code(" ES040MSBT000030607 ") == "ES040MSBT000030607"


def test_a_dataset_lists_each_source_its_piezometers_name() -> None:
    near = _point()
    with pytest.raises(ValidationError, match="unlisted sources"):
        PiezometryDataset(
            sources=(SOURCE,),
            piezometers_read=1,
            levels_read=1,
            left_out=0,
            piezometers=(near.model_copy(update={"sources": (JUCAR,)}),),
        )
    with pytest.raises(ValidationError, match="listed once"):
        PiezometryDataset(
            sources=(SOURCE, SOURCE),
            piezometers_read=1,
            levels_read=1,
            left_out=0,
            piezometers=(near,),
        )


def test_a_basin_service_must_be_catalogued_and_read_once() -> None:
    settings = load_settings()
    basins = settings.piezometry.basins
    for wrong in (
        [basins[0].model_copy(update={"service": "no-such-service"})],
        [basins[0], basins[0]],
    ):
        data = settings.model_dump()
        data["piezometry"]["basins"] = [b.model_dump() for b in wrong]
        with pytest.raises(ValidationError):
            Settings.model_validate(data)


def test_a_guadiana_sheet_skips_notes_and_needs_the_ground(tmp_path: Path) -> None:
    """Cells that are not numbers are skipped, a "12,5" reads as 12.5, and a station with
    no ground elevation gives no level (none is guessed)."""
    from openpyxl import Workbook

    basin = _basin(GuadianaBasin)
    columns = basin.columns
    book = Workbook()
    levels = book.active
    assert levels is not None
    levels.title = basin.levels_sheet
    levels.append(["1", "2", "3"])
    months = [datetime(2026, m, 1) for m in (1, 2, 3, 4, 5)]
    levels.append(["TÉRMINO", "MASA", columns.code, *months, "Fecha"])
    levels.append(["A", "B", "X.1", 10.0, "12,5", "seca", True, float("nan")])
    levels.append(["A", "B", "X.2", 10.0])
    levels.append(["A", "B", "X.3"])
    levels.append(["A", "B", "unknown", 1.0])
    stations = book.create_sheet(basin.stations_sheet)
    stations.append(
        [columns.station_code, columns.x, columns.y, columns.ground, columns.body_label]
    )
    stations.append(["X.1", 500000, 4400000, 700.0, "BULLAQUE"])
    stations.append(["X.2", 500000, 4400000, None, "BULLAQUE"])
    stations.append(["X.3", 500000, 4400000, 650.0, "BULLAQUE"])
    stations.append(["X.4", None, 4400000, 650.0, "BULLAQUE"])
    stations.append([None, 500000, 4400000, 650.0, "BULLAQUE"])
    path = tmp_path / "guadiana.xlsx"
    book.save(path)
    found = read_basin(basin, path)
    assert set(found.stations) == {"X.1", "X.2", "X.3"}
    assert found.levels["X.1"] == [(date(2026, 1, 1), 690.0), (date(2026, 2, 1), 687.5)]
    assert "X.2" not in found.levels
    # Months read: X.1's four filled cells (a NaN is saved empty) and X.2's one.
    assert found.rows_read == 5
    no_months = basin.model_copy(update={"header_row": 3})
    with pytest.raises(PiezometryReadError, match="lacks the columns"):
        read_basin(no_months, path)
