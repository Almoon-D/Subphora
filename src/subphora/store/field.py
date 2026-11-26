# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The server's store of field observations: SQLite for the records, a folder for their
files (``data/field/``, git-ignored; hard rules 5 and 6).

The store is append-only and idempotent. A record is kept as its canonical JSON under its
id: the same id sent again with the same content is a duplicate, with different content
a conflict, and the first copy is never overwritten. A file is written whole (a temporary
file renamed into place) before its row says it is stored, so a failure half-way leaves
no file the store claims. SQLite's calls block, so each runs in a worker thread.
"""

import asyncio
import contextlib
import os
import sqlite3
import tempfile
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

from subphora.domain.field import (
    MEDIA_FAMILIES,
    FieldError,
    FieldFailure,
    FieldSummary,
    KindCount,
    Media,
    Observation,
    ObservationKind,
    Outcome,
    SyncResult,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    track_id TEXT,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY REFERENCES observations(id),
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    file TEXT NOT NULL,
    received_at TEXT NOT NULL
) STRICT;
"""


class FieldStore:
    def __init__(self, database: Path, media_dir: Path, busy_timeout_s: float) -> None:
        self._database = database
        self._media_dir = media_dir
        self._timeout = busy_timeout_s
        # One writer at a time in this process; SQLite's busy timeout covers the others.
        self._lock = asyncio.Lock()

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            self._database.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._database, timeout=self._timeout)
        except (OSError, sqlite3.Error) as exc:
            raise FieldError(FieldFailure.STORE_UNAVAILABLE, "the store cannot be opened") from exc
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(_SCHEMA)
            yield connection
        except sqlite3.Error as exc:
            raise FieldError(FieldFailure.STORE_UNAVAILABLE, "the store failed") from exc
        finally:
            connection.close()

    async def upsert(self, observations: Sequence[Observation]) -> tuple[SyncResult, ...]:
        """Store every new record in one transaction; report each one's outcome."""
        async with self._lock:
            return await asyncio.to_thread(self._upsert, observations)

    def _upsert(self, observations: Sequence[Observation]) -> tuple[SyncResult, ...]:
        received = datetime.now(UTC).isoformat()
        results: list[SyncResult] = []
        with self._connect() as db, db:
            for observation in observations:
                body = observation.model_dump_json()
                inserted = db.execute(
                    "INSERT INTO observations (id, kind, recorded_at, track_id, body,"
                    " received_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                    (
                        observation.id,
                        observation.kind.value,
                        observation.recorded_at.isoformat(),
                        observation.track_id,
                        body,
                        received,
                    ),
                ).rowcount
                if inserted:
                    outcome = Outcome.CREATED
                else:
                    (stored,) = db.execute(
                        "SELECT body FROM observations WHERE id = ?", (observation.id,)
                    ).fetchone()
                    outcome = Outcome.DUPLICATE if stored == body else Outcome.CONFLICT
                results.append(SyncResult(id=observation.id, outcome=outcome))
        return tuple(results)

    async def observation(self, observation_id: str) -> Observation | None:
        return await asyncio.to_thread(self._observation, observation_id)

    def _observation(self, observation_id: str) -> Observation | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT body FROM observations WHERE id = ?", (observation_id,)
            ).fetchone()
        return None if row is None else Observation.model_validate_json(row[0])

    async def put_media(
        self, observation_id: str, media: Media, extension: str, content: bytes
    ) -> Outcome:
        """Store a record's file, already checked against what the record declared."""
        async with self._lock:
            return await asyncio.to_thread(
                self._put_media, observation_id, media, extension, content
            )

    def _put_media(
        self, observation_id: str, media: Media, extension: str, content: bytes
    ) -> Outcome:
        with self._connect() as db:
            if db.execute("SELECT 1 FROM media WHERE id = ?", (observation_id,)).fetchone():
                return Outcome.DUPLICATE
            name = f"{observation_id}.{extension}"
            self._write_file(name, content)
            with db:
                db.execute(
                    "INSERT INTO media (id, content_type, size_bytes, sha256, file, received_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        observation_id,
                        media.content_type,
                        media.size_bytes,
                        media.sha256,
                        name,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        return Outcome.CREATED

    def _write_file(self, name: str, content: bytes) -> None:
        try:
            self._media_dir.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self._media_dir, prefix=".incoming-")
            try:
                with os.fdopen(handle, "wb") as file:
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                Path(temporary).replace(self._media_dir / name)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise FieldError(FieldFailure.STORE_UNAVAILABLE, "the file cannot be written") from exc

    async def summary(self) -> FieldSummary:
        return await asyncio.to_thread(self._summary)

    def _summary(self) -> FieldSummary:
        with self._connect() as db:
            counts = dict(
                db.execute("SELECT kind, COUNT(*) FROM observations GROUP BY kind").fetchall()
            )
            media = dict(
                db.execute(
                    "SELECT o.kind, COUNT(*) FROM media m JOIN observations o ON o.id = m.id"
                    " GROUP BY o.kind"
                ).fetchall()
            )
            (tracks,) = db.execute(
                "SELECT COUNT(DISTINCT track_id) FROM observations WHERE track_id IS NOT NULL"
            ).fetchone()
            first, last = db.execute(
                "SELECT MIN(recorded_at), MAX(recorded_at) FROM observations"
            ).fetchone()
        kinds = tuple(
            KindCount(
                kind=kind,
                records=counts.get(kind.value, 0),
                with_media=media.get(kind.value, 0) if kind in MEDIA_FAMILIES else 0,
            )
            for kind in ObservationKind
        )
        return FieldSummary(
            kinds=kinds,
            tracks=tracks,
            first_recorded_at=datetime.fromisoformat(first) if first else None,
            last_recorded_at=datetime.fromisoformat(last) if last else None,
        )
