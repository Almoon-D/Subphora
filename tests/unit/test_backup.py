# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Backups of data/ (MASTER_PLAN §4.9): an archive of every file but the cache, SQLite
databases copied consistently while open, the read-back check (the restore test) and each
way it refuses an archive, a restore that keeps what it replaces, pruning, the nightly
schedule, and ``subphora backup``. Every file is synthetic."""

import asyncio
import gzip
import io
import sqlite3
import tarfile
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import subphora.__main__ as cli
import subphora.config
from subphora.config import Settings
from subphora.domain.backup import BackupError, BackupFailure
from subphora.services.backup import BackupService, next_run
from subphora.store.backup import (
    MANIFEST,
    archive_name,
    archives,
    create_backup,
    prune,
    restore_backup,
    verify_backup,
)
from tests.support import fast_settings

NOW = datetime(2026, 11, 26, 2, 30, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


def make_data(root: Path) -> Path:
    data = root / "data"
    (data / "field" / "media").mkdir(parents=True)
    (data / "cache" / "ign").mkdir(parents=True)
    (data / "national").mkdir()
    (data / "national" / "index.pmtiles").write_bytes(b"synthetic tiles" * 100)
    (data / "field" / "media" / "a.jpg").write_bytes(b"\xff\xd8 synthetic photo")
    (data / "cache" / "ign" / "tile.png").write_bytes(b"cached, downloaded again on demand")
    with closing(sqlite3.connect(data / "field" / "field.sqlite")) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE observations (id TEXT PRIMARY KEY, body TEXT)")
        db.execute("INSERT INTO observations VALUES ('one', 'a synthetic note')")
        db.commit()
    return data


def rows(database: Path) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(database)) as db:
        return db.execute("SELECT * FROM observations ORDER BY id").fetchall()


def backup(data: Path, destination: Path, at: datetime = NOW) -> Path:
    summary = create_backup(data, destination, ("cache",), at, "0.0.0")
    return destination / summary.archive


def members(archive: Path) -> list[str]:
    with tarfile.open(archive) as tar:
        return sorted(tar.getnames())


# ── The archive ─────────────────────────────────────────────────────────────────────


def test_an_archive_holds_every_file_but_the_cache_and_a_manifest(tmp_path: Path) -> None:
    data = make_data(tmp_path)
    archive = backup(data, tmp_path / "backups")
    assert archive.name == "subphora-20261126T023000000000Z.tar.gz"
    assert members(archive) == [
        "data/field/field.sqlite",
        "data/field/media/a.jpg",
        "data/national/index.pmtiles",
        MANIFEST,
    ]
    summary = verify_backup(archive)
    assert (summary.files, summary.databases) == (3, 1)
    assert summary.size_bytes == archive.stat().st_size


def test_a_database_open_for_writing_is_copied_whole(tmp_path: Path) -> None:
    data = make_data(tmp_path)
    database = data / "field" / "field.sqlite"
    # A writer holds the database with a change still only in its write-ahead log.
    writer = sqlite3.connect(database)
    try:
        writer.execute("INSERT INTO observations VALUES ('two', 'written while backing up')")
        writer.commit()
        assert (data / "field" / "field.sqlite-wal").exists()
        archive = backup(data, tmp_path / "backups")
    finally:
        writer.close()
    assert "data/field/field.sqlite-wal" not in members(archive)
    restored = tmp_path / "restored"
    restore_backup(archive, restored, NOW)
    assert rows(restored / "field" / "field.sqlite") == [
        ("one", "a synthetic note"),
        ("two", "written while backing up"),
    ]


def test_the_destination_cannot_be_inside_the_data(tmp_path: Path) -> None:
    data = make_data(tmp_path)
    with pytest.raises(BackupError) as inside:
        backup(data, data / "backups")
    assert inside.value.failure is BackupFailure.DESTINATION_INSIDE_SOURCE
    with pytest.raises(BackupError) as missing:
        backup(tmp_path / "nowhere", tmp_path / "backups")
    assert missing.value.failure is BackupFailure.NO_SOURCE


def test_a_failed_write_leaves_no_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = make_data(tmp_path)
    destination = tmp_path / "backups"

    def full_disk(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("No space left on device")

    monkeypatch.setattr(tarfile.TarFile, "addfile", full_disk)
    with pytest.raises(BackupError) as failed:
        backup(data, destination)
    assert failed.value.failure is BackupFailure.UNREADABLE
    assert list(destination.iterdir()) == []


# ── The read-back check ───────────────────────────────────────────────────────────────


def rewrite(archive: Path, change: Any) -> None:
    """Rewrite an archive member by member through ``change(name, bytes)``, which returns
    the new (name, bytes) or None to leave the member out."""
    with tarfile.open(archive) as tar:
        items = [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]  # type: ignore[union-attr]
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in items:
            changed = change(name, content)
            if changed is None:
                continue
            info = tarfile.TarInfo(changed[0])
            info.size = len(changed[1])
            tar.addfile(info, io.BytesIO(changed[1]))


@pytest.mark.parametrize(
    ("change", "failure"),
    [
        (lambda n, c: (n, c + b"!") if n.endswith("a.jpg") else (n, c), "checksum_mismatch"),
        (lambda n, c: None if n.endswith("a.jpg") else (n, c), "missing_file"),
        (lambda n, c: None if n == MANIFEST else (n, c), "no_manifest"),
        (lambda n, c: (n, b"{}") if n == MANIFEST else (n, c), "no_manifest"),
        (lambda n, c: ("data/../../etc/x", c) if n.endswith("a.jpg") else (n, c), "unsafe_path"),
        (lambda n, c: ("/etc/x", c) if n.endswith("a.jpg") else (n, c), "unsafe_path"),
        (lambda n, c: ("data/extra.txt", c) if n.endswith("a.jpg") else (n, c), "unlisted_file"),
    ],
    ids=["changed", "missing", "no manifest", "bad manifest", "parent", "absolute", "unlisted"],
)
def test_the_check_refuses_a_damaged_archive(tmp_path: Path, change: Any, failure: str) -> None:
    archive = backup(make_data(tmp_path), tmp_path / "backups")
    rewrite(archive, change)
    with pytest.raises(BackupError) as refused:
        verify_backup(archive)
    assert refused.value.failure.value == failure
    # A refused archive is never restored.
    target = tmp_path / "data"
    before = sorted(p.name for p in target.iterdir())
    with pytest.raises(BackupError):
        restore_backup(archive, target, NOW)
    assert sorted(p.name for p in target.iterdir()) == before


def test_the_check_refuses_a_damaged_database(tmp_path: Path) -> None:
    archive = backup(make_data(tmp_path), tmp_path / "backups")
    import hashlib
    import json

    garbage = b"SQLite format 3\x00" + b"\x00" * 200

    def damage(name: str, content: bytes) -> tuple[str, bytes]:
        if name.endswith("field.sqlite"):
            return name, garbage
        if name == MANIFEST:
            manifest = json.loads(content)
            for entry in manifest["files"]:
                if entry["database"]:
                    entry["size_bytes"] = len(garbage)
                    entry["sha256"] = hashlib.sha256(garbage).hexdigest()
            return name, json.dumps(manifest).encode()
        return name, content

    rewrite(archive, damage)
    with pytest.raises(BackupError) as refused:
        verify_backup(archive)
    assert refused.value.failure is BackupFailure.DATABASE_DAMAGED


@pytest.mark.parametrize("content", [b"", b"not a tar", gzip.compress(b"not a tar")])
def test_the_check_refuses_an_unreadable_file(tmp_path: Path, content: bytes) -> None:
    archive = tmp_path / "subphora-x.tar.gz"
    archive.write_bytes(content)
    with pytest.raises(BackupError) as refused:
        verify_backup(archive)
    assert refused.value.failure is BackupFailure.UNREADABLE
    with pytest.raises(BackupError):
        verify_backup(tmp_path / "missing.tar.gz")


# ── The restore ─────────────────────────────────────────────────────────────────────


def test_a_restore_keeps_what_it_replaces_and_the_cache(tmp_path: Path) -> None:
    data = make_data(tmp_path)
    archive = backup(data, tmp_path / "backups")
    # After the backup: a note lost, a photo added.
    with closing(sqlite3.connect(data / "field" / "field.sqlite")) as db:
        db.execute("DELETE FROM observations")
        db.commit()
    (data / "field" / "media" / "b.jpg").write_bytes(b"a later photo")
    previous = restore_backup(archive, data, NOW)
    assert rows(data / "field" / "field.sqlite") == [("one", "a synthetic note")]
    assert not (data / "field" / "media" / "b.jpg").exists()
    assert (data / "cache" / "ign" / "tile.png").exists()
    assert previous == data / ".before-restore-20261126T023000Z"
    assert (previous / "field" / "media" / "b.jpg").read_bytes() == b"a later photo"
    assert not any(p.name.startswith(".restoring-") for p in data.iterdir())
    # What a restore kept aside is never backed up again.
    again = backup(data, tmp_path / "backups", NOW + timedelta(days=1))
    assert not any(".before-restore-" in name for name in members(again))


def test_a_restore_into_an_empty_place_moves_nothing_aside(tmp_path: Path) -> None:
    archive = backup(make_data(tmp_path), tmp_path / "backups")
    target = tmp_path / "new-computer" / "data"
    assert restore_backup(archive, target, NOW) is None
    assert (target / "national" / "index.pmtiles").read_bytes() == b"synthetic tiles" * 100


def test_a_restore_cut_while_unpacking_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = make_data(tmp_path)
    archive = backup(data, tmp_path / "backups")
    (data / "later.txt").write_text("written after the backup")
    import shutil

    def cut(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("the disk went away")

    monkeypatch.setattr(shutil, "copyfileobj", cut)
    with pytest.raises(BackupError, match="went away"):
        restore_backup(archive, data, NOW)
    assert (data / "later.txt").exists()
    assert not any(p.name.startswith(".") for p in data.iterdir())


# ── Pruning and the nightly run ───────────────────────────────────────────────────────


def test_pruning_keeps_the_newest(tmp_path: Path) -> None:
    destination = tmp_path / "backups"
    destination.mkdir()
    names = [archive_name(NOW + timedelta(days=d)) for d in range(5)]
    for name in names:
        (destination / name).write_bytes(b"x")
    (destination / "notes.txt").write_text("not an archive, never touched")
    assert prune(destination, 2) == names[:3]
    assert [p.name for p in archives(destination)] == names[3:]
    assert (destination / "notes.txt").exists()
    assert archives(tmp_path / "none") == []


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # 03:00 in Madrid (winter, UTC+1) is 02:00 UTC: tonight's 03:30 is 02:30 UTC.
        (datetime(2026, 11, 26, 2, 0, tzinfo=UTC), datetime(2026, 11, 26, 2, 30, tzinfo=UTC)),
        # Just after it: the next night.
        (datetime(2026, 11, 26, 2, 30, tzinfo=UTC), datetime(2026, 11, 27, 2, 30, tzinfo=UTC)),
        # Summer time (UTC+2): 03:30 is 01:30 UTC.
        (datetime(2026, 7, 1, 12, 0, tzinfo=UTC), datetime(2026, 7, 2, 1, 30, tzinfo=UTC)),
    ],
)
def test_the_nightly_time_is_local(settings: Settings, now: datetime, expected: datetime) -> None:
    assert next_run(now, settings) == expected


def backup_settings(settings: Settings, root: Path) -> Settings:
    update = {"destination": root / "backups", "keep": 2}
    return settings.model_copy(update={"backup": settings.backup.model_copy(update=update)})


def test_the_nightly_run_backs_up_verifies_prunes_and_survives_a_failure(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    make_data(tmp_path)
    settings = backup_settings(settings, tmp_path)
    times: Iterator[datetime] = iter(NOW + timedelta(days=d) for d in range(100))
    service = BackupService(settings, tmp_path, clock=lambda: next(times))
    nights = 0

    async def sleep(seconds: float) -> None:
        nonlocal nights
        assert 0 < seconds <= 86400
        nights += 1
        if nights == 3:
            # The third night the data folder is gone: logged, and the loop goes on.
            (tmp_path / "data").rename(tmp_path / "elsewhere")
        if nights == 5:
            raise asyncio.CancelledError

    caplog.set_level("INFO")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.nightly(sleep))
    assert len(archives(tmp_path / "backups")) == 2
    assert "the nightly backup failed (no_source)" in caplog.text
    assert "verified" in caplog.text


# ── subphora backup ───────────────────────────────────────────────────────────────────


def test_the_backup_command_creates_lists_verifies_and_restores(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    make_data(tmp_path)
    monkeypatch.setattr(subphora.config, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: backup_settings(settings, tmp_path))
    assert cli.main(["backup", "list"]) == 0
    assert "no archives yet" in capsys.readouterr().out
    assert cli.main(["backup", "create"]) == 0
    assert "written and verified; 3 files (1 databases)" in capsys.readouterr().out
    assert cli.main(["backup", "list"]) == 0
    name = capsys.readouterr().out.strip()
    archive = tmp_path / "backups" / name
    assert cli.main(["backup", "verify", str(archive)]) == 0
    assert "verified" in capsys.readouterr().out
    assert cli.main(["backup", "restore", str(archive)]) == 0
    assert "kept in" in capsys.readouterr().out
    archive.write_bytes(b"damaged")
    assert cli.main(["backup", "verify", str(archive)]) == cli.EXIT_FAILED_CHECK
    assert "FAILED (unreadable)" in capsys.readouterr().out


def test_the_settings_refuse_a_bad_exclusion_or_zone(settings: Settings) -> None:
    from pydantic import ValidationError

    from subphora.config.backup import BackupSettings

    raw = settings.backup.model_dump()
    with pytest.raises(ValidationError, match="top-level folder"):
        BackupSettings.model_validate(raw | {"exclude": ["cache/ign"]})
    with pytest.raises(ValidationError, match="not a time zone"):
        BackupSettings.model_validate(raw | {"nightly": {"at": "03:30", "timezone": "Mars/Base"}})
    assert settings.backup.source_path(Path("/r")) == Path("/r/data")
    absolute = settings.backup.model_copy(update={"destination": Path("/mnt/usb")})
    assert absolute.destination_path(Path("/r")) == Path("/mnt/usb")
