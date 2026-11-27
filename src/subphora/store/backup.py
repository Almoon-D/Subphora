# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Backups of the private data folder (MASTER_PLAN §4.9): one ``.tar.gz`` per run.

An archive holds every file of the folder except the excluded top-level folders, and a
``manifest.json`` with each file's size and SHA-256. SQLite databases are copied with
SQLite's own backup, so a database being written while the backup runs is copied whole
and consistent (its ``-wal`` and ``-shm`` files are never copied). An archive is written
under a temporary name and renamed when complete, so a cut run leaves no archive that
looks whole. A restore checks the archive first, unpacks it inside the folder, moves the
files that were there into a dated folder beside them (never deleted) and puts the
restored ones in their place.
"""

import contextlib
import hashlib
import io
import os
import shutil
import sqlite3
import tarfile
import tempfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from subphora.domain.backup import (
    BackupEntry,
    BackupError,
    BackupFailure,
    BackupManifest,
    BackupSummary,
)

MANIFEST = "manifest.json"
PREFIX = "subphora-"
SUFFIX = ".tar.gz"
_DATA = "data"
_SQLITE_HEADER = b"SQLite format 3\x00"
_SQLITE_SIDECARS = ("-wal", "-shm", "-journal")
_CHUNK = 1 << 20
RESTORING = ".restoring-"
BEFORE_RESTORE = ".before-restore-"


def archive_name(created_at: datetime) -> str:
    return f"{PREFIX}{created_at.strftime('%Y%m%dT%H%M%S%fZ')}{SUFFIX}"


def archives(destination: Path) -> list[Path]:
    """The archives in a destination, oldest first (their names sort by time)."""
    if not destination.is_dir():
        return []
    return sorted(
        p for p in destination.iterdir() if p.name.startswith(PREFIX) and p.name.endswith(SUFFIX)
    )


def _is_database(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(len(_SQLITE_HEADER)) == _SQLITE_HEADER


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _files(source: Path, exclude: tuple[str, ...]) -> Iterator[Path]:
    for folder, dirs, names in os.walk(source):
        here = Path(folder)
        if here == source:
            dirs[:] = [d for d in dirs if d not in exclude and not _ours(d)]
        dirs.sort()
        for name in sorted(names):
            path = here / name
            if path.is_symlink() or not path.is_file():
                continue
            if here == source and name in exclude:
                continue
            yield path


def _copy_database(path: Path, target: Path) -> None:
    source = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)
            # The copy is one self-contained file, whatever journal mode the source uses.
            copy.execute("PRAGMA journal_mode=DELETE")
        finally:
            copy.close()
    finally:
        source.close()


def create_backup(
    source: Path, destination: Path, exclude: tuple[str, ...], created_at: datetime, version: str
) -> BackupSummary:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        raise BackupError(BackupFailure.NO_SOURCE, f"there is no folder {source.name!r} to back up")
    if destination == source or destination.is_relative_to(source):
        raise BackupError(
            BackupFailure.DESTINATION_INSIDE_SOURCE,
            "the destination is inside the backed-up folder; choose another place",
        )
    destination.mkdir(parents=True, exist_ok=True)
    name = archive_name(created_at)
    partial = destination / f".{name}.partial"
    entries: list[BackupEntry] = []
    try:
        with (
            tempfile.TemporaryDirectory(prefix="subphora-backup-") as scratch,
            tarfile.open(partial, "w:gz") as tar,
        ):
            databases = {
                path
                for path in _files(source, exclude)
                if not path.name.endswith(_SQLITE_SIDECARS) and _is_database(path)
            }
            sidecars = {
                path.with_name(path.name + suffix)
                for path in databases
                for suffix in _SQLITE_SIDECARS
            }
            for path in _files(source, exclude):
                if path in sidecars:
                    continue
                relative = path.relative_to(source).as_posix()
                stored = path
                if path in databases:
                    stored = Path(scratch) / f"{len(entries)}.sqlite"
                    _copy_database(path, stored)
                entries.append(
                    BackupEntry(
                        path=relative,
                        size_bytes=stored.stat().st_size,
                        sha256=_sha256(stored),
                        database=path in databases,
                    )
                )
                tar.add(stored, arcname=f"{_DATA}/{relative}", recursive=False)
            manifest = BackupManifest(
                created_at=created_at, version=version, excluded=exclude, files=tuple(entries)
            )
            body = manifest.model_dump_json(indent=2).encode("utf-8")
            info = tarfile.TarInfo(MANIFEST)
            info.size = len(body)
            info.mtime = int(created_at.timestamp())
            tar.addfile(info, io.BytesIO(body))
        partial.rename(destination / name)
    except (OSError, sqlite3.Error, tarfile.TarError) as exc:
        partial.unlink(missing_ok=True)
        raise BackupError(BackupFailure.UNREADABLE, f"the backup failed: {exc}") from exc
    return _summary(name, manifest, destination / name)


def _summary(name: str, manifest: BackupManifest, archive: Path) -> BackupSummary:
    return BackupSummary(
        archive=name,
        created_at=manifest.created_at,
        files=len(manifest.files),
        databases=sum(1 for entry in manifest.files if entry.database),
        size_bytes=archive.stat().st_size,
    )


def prune(destination: Path, keep: int) -> list[str]:
    """Delete all but the newest ``keep`` archives; the names deleted."""
    old = archives(destination)[:-keep] if keep > 0 else []
    for path in old:
        path.unlink(missing_ok=True)
    return [path.name for path in old]


def _safe_member(name: str) -> str:
    """The member's path inside ``data/``, refusing anything that could leave it."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 2 or path.parts[0] != _DATA:
        raise BackupError(BackupFailure.UNSAFE_PATH, f"the archive holds an unsafe path {name!r}")
    return path.relative_to(_DATA).as_posix()


@contextlib.contextmanager
def _open(archive: Path) -> Iterator[tarfile.TarFile]:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            yield tar
    except (OSError, tarfile.TarError, EOFError) as exc:
        raise BackupError(BackupFailure.UNREADABLE, f"the archive cannot be read: {exc}") from exc


def _manifest(tar: tarfile.TarFile) -> BackupManifest:
    try:
        member = tar.getmember(MANIFEST)
    except KeyError:
        raise BackupError(BackupFailure.NO_MANIFEST, "the archive has no manifest") from None
    handle = tar.extractfile(member)
    if handle is None:
        raise BackupError(BackupFailure.NO_MANIFEST, "the archive's manifest is not a file")
    try:
        return BackupManifest.model_validate_json(handle.read())
    except ValidationError as exc:
        raise BackupError(BackupFailure.NO_MANIFEST, "the archive's manifest is not valid") from exc


def verify_backup(archive: Path) -> BackupSummary:
    """Read the whole archive back: every listed file present with its size and SHA-256,
    nothing unlisted, no path that leaves the folder, every database passing SQLite's
    integrity check. This is the restore test the nightly run does after each backup."""
    with _open(archive) as tar, tempfile.TemporaryDirectory(prefix="subphora-verify-") as scratch:
        manifest = _manifest(tar)
        listed = {entry.path: entry for entry in manifest.files}
        seen: set[str] = set()
        for member in tar.getmembers():
            if member.name == MANIFEST:
                continue
            relative = _safe_member(member.name)
            if not member.isfile():
                raise BackupError(BackupFailure.UNSAFE_PATH, f"{relative!r} is not a plain file")
            entry = listed.get(relative)
            if entry is None:
                raise BackupError(
                    BackupFailure.UNLISTED_FILE, f"{relative!r} is not in the manifest"
                )
            handle = tar.extractfile(member)
            if handle is None:  # pragma: no cover - a plain file always has content
                raise BackupError(BackupFailure.UNREADABLE, f"{relative!r} cannot be read")
            digest = hashlib.sha256()
            target = Path(scratch) / "database.sqlite"
            with contextlib.ExitStack() as stack:
                out = stack.enter_context(target.open("wb")) if entry.database else None
                while chunk := handle.read(_CHUNK):
                    digest.update(chunk)
                    if out is not None:
                        out.write(chunk)
            if member.size != entry.size_bytes or digest.hexdigest() != entry.sha256:
                raise BackupError(BackupFailure.CHECKSUM_MISMATCH, f"{relative!r} has changed")
            if entry.database:
                _check_database(target, relative)
            seen.add(relative)
        missing = sorted(set(listed) - seen)
        if missing:
            raise BackupError(BackupFailure.MISSING_FILE, f"{missing[0]!r} is missing")
    return _summary(archive.name, manifest, archive)


def _check_database(path: Path, relative: str) -> None:
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise BackupError(BackupFailure.DATABASE_DAMAGED, f"{relative!r} is damaged") from exc
    if result is None or result[0] != "ok":
        raise BackupError(BackupFailure.DATABASE_DAMAGED, f"{relative!r} is damaged")


def restore_backup(archive: Path, target: Path, restored_at: datetime) -> Path | None:
    """Put the archive's files in place of those of ``target``; returns the folder inside
    it where the files that were there were moved (kept, never deleted), or None if there
    were none. Everything happens inside ``target``, which may be a mounted volume that
    cannot itself be renamed; the excluded folders (the cache) stay where they are."""
    verify_backup(archive)
    target.mkdir(parents=True, exist_ok=True)
    stamp = restored_at.strftime("%Y%m%dT%H%M%SZ")
    staging = target / f"{RESTORING}{stamp}"
    previous = target / f"{BEFORE_RESTORE}{stamp}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        with _open(archive) as tar:
            manifest = _manifest(tar)
            for member in tar.getmembers():
                if member.name == MANIFEST:
                    continue
                relative = _safe_member(member.name)
                handle = tar.extractfile(member)
                if handle is None:  # pragma: no cover - verified as plain files above
                    continue
                path = staging / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("wb") as out:
                    shutil.copyfileobj(handle, out, _CHUNK)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    kept = {*manifest.excluded, staging.name, previous.name}
    current = [p for p in target.iterdir() if p.name not in kept and not _ours(p.name)]
    if current:
        previous.mkdir()
        for path in current:
            path.rename(previous / path.name)
    for path in staging.iterdir():
        path.rename(target / path.name)
    staging.rmdir()
    return previous if current else None


def _ours(name: str) -> bool:
    """A folder a restore made inside the data folder, never backed up or moved."""
    return name.startswith((RESTORING, BEFORE_RESTORE))
