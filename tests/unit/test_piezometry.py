# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Importing the national piezometry database (MASTER_PLAN §4.3, depth): an Access file
read by mdb-export (a stand-in script here, printing excerpts of the real tables), the
summary per piezometer, the UTM zone of each row, and every way the import fails."""

import stat
import sys
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from subphora.__main__ import main
from subphora.config import Settings, load_settings
from subphora.domain.piezometry import Piezometer, PiezometryDataset
from subphora.services.piezometry import import_piezometry, piezometer_points, summarise
from subphora.sources.piezometry import PiezometryReadError, access_file, export_table
from subphora.store.piezometry import read_piezometry
from tests.unit.test_depth import SOURCE

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "piezometry"
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


def settings_for(path: Path, mdb_export: str, tmp_path: Path, **summary: float) -> Settings:
    settings = load_settings()
    piezometry = settings.piezometry.model_copy(
        update={
            "input": path,
            "output": tmp_path / "out" / "piezometers.json",
            "mdb_export": mdb_export,
            "summary": settings.piezometry.summary.model_copy(update=summary),
        }
    )
    return settings.model_copy(update={"piezometry": piezometry})


def test_the_import_summarises_each_piezometer_with_recent_levels(
    tmp_path: Path, fake_mdb_export: str
) -> None:
    settings = settings_for(database(tmp_path), fake_mdb_export, tmp_path)
    dataset = import_piezometry(settings, tmp_path, NOW)
    assert dataset.piezometers_read == 5
    assert dataset.levels_read == 81
    # Left out: the removed one (last level before 2008) and the one with no body.
    assert dataset.left_out == 2
    by_id = {p.id: p for p in dataset.piezometers}
    assert set(by_id) == {1549, 1550, 6438}
    porches = by_id[1549]
    assert porches.name == "Los Porches"
    assert porches.body == "ES040MSBT000030607"
    assert porches.body_label == "Sierra de Altomira"
    assert porches.ground_m == 703.67
    assert porches.level_low_m <= porches.level_m <= porches.level_high_m
    assert porches.last.year == 2024
    # Zone 30, in Cuenca; zone 31 (despite the column name), in Catalonia.
    assert -2.8 < porches.longitude < -2.7
    assert 39.4 < porches.latitude < 39.5
    assert by_id[6438].longitude > 0.5
    assert len(dataset.sha256) == 64
    assert dataset.source.service_id == "miteco-piezometry-db"
    assert dataset.source.file_name == "basedatospiezometria.zip"
    assert dataset.source.levels_to == max(p.last for p in dataset.piezometers)
    assert read_piezometry(tmp_path / "out" / "piezometers.json") == dataset


def test_an_access_file_can_be_read_without_a_zip(tmp_path: Path, fake_mdb_export: str) -> None:
    rows = list(export_table(database(tmp_path, zipped=False), "01_Piezometros", fake_mdb_export))
    assert [r["IDPIEZ"] for r in rows] == ["1549", "1550", "6438", "1591", "5705"]


def test_a_level_is_the_recent_median_and_too_few_or_too_old_are_left_out() -> None:
    settings = load_settings().piezometry
    levels = [(date(2024, month, 1), float(month)) for month in range(1, 13)]
    summary = summarise(levels, settings, date(2026, 11, 26))
    assert summary is not None
    assert summary.level == pytest.approx(6.5)
    assert summary.low < summary.level < summary.high
    assert summary.count == 12
    # Only the recent window counts: a level 20 years before the last is not in it.
    with_old = summarise([(date(2004, 1, 1), 999.0), *levels], settings, date(2026, 11, 26))
    assert with_old is not None
    assert with_old.count == 12
    assert summarise(levels[:3], settings, date(2026, 11, 26)) is None
    assert summarise(levels, settings, date(2045, 1, 1)) is None
    assert summarise([], settings, date(2026, 11, 26)) is None


def test_piezometers_are_projected_and_kept_only_near_the_area() -> None:
    near = Piezometer(
        id=1,
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
    )
    far = near.model_copy(update={"id": 2, "longitude": -3.0})
    dataset = PiezometryDataset(
        source=SOURCE,
        sha256="0" * 64,
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
    output = tmp_path / "levels.json"
    (owner / "owner.yaml").write_text(
        f"piezometry:\n  mdb_export: {fake_mdb_export}\n  output: {output}\n", encoding="utf-8"
    )
    monkeypatch.setattr("subphora.__main__.load_settings", lambda: load_settings(owner))
    assert main(["piezometry", "import", "--file", str(database(tmp_path))]) == 0
    printed = capsys.readouterr().out
    assert "3 piezometers kept of 5 (2 left out)" in printed
    assert output.exists()
    assert main(["piezometry", "import", "--file", str(tmp_path / "absent.zip")]) == 1
    assert "FAILED" in capsys.readouterr().out
