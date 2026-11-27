# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The owner's well registry: one SQLite database in ``data/wells/`` (git-ignored; hard
rule 6, MASTER_PLAN §3 Privacy).

A well is kept as its canonical JSON under its id; the app may replace it (the owner
corrects a record) or delete it with its readings. A reading is kept once under its id:
the same id with the same content again changes nothing, with other content it is a
conflict and the first copy stays. An import writes everything in one transaction and,
unlike the app, never replaces a well it already holds with different content: such a row
is a conflict. Nothing here logs a record's content. SQLite's calls block, so each runs in
a worker thread.
"""

import asyncio
import contextlib
import sqlite3
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

from subphora.domain.wells import (
    Change,
    ImportReport,
    Well,
    WellReading,
    WellRecord,
    WellsError,
    WellsFailure,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wells (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    saved_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS readings (
    id TEXT PRIMARY KEY,
    well_id TEXT NOT NULL REFERENCES wells(id) ON DELETE CASCADE,
    measured_at TEXT NOT NULL,
    body TEXT NOT NULL,
    saved_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS readings_by_well ON readings (well_id, measured_at);
"""


class WellsStore:
    def __init__(self, database: Path, busy_timeout_s: float) -> None:
        self._database = database
        self._timeout = busy_timeout_s
        # One writer at a time in this process; SQLite's busy timeout covers the others.
        self._lock = asyncio.Lock()

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            self._database.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._database, timeout=self._timeout)
        except (OSError, sqlite3.Error) as exc:
            raise WellsError(
                WellsFailure.STORE_UNAVAILABLE, "the registry cannot be opened"
            ) from exc
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(_SCHEMA)
            yield connection
        except sqlite3.Error as exc:
            raise WellsError(WellsFailure.STORE_UNAVAILABLE, "the registry failed") from exc
        finally:
            connection.close()

    # ── Wells ──────────────────────────────────────────────────────────────────────────

    async def put(self, well: Well) -> Change:
        """Store a well, replacing the one under its id."""
        async with self._lock:
            return await asyncio.to_thread(self._put, well)

    def _put(self, well: Well) -> Change:
        body = well.model_dump_json()
        with self._connect() as db, db:
            row = db.execute("SELECT body FROM wells WHERE id = ?", (well.id,)).fetchone()
            if row is not None and row[0] == body:
                return Change.UNCHANGED
            db.execute(
                "INSERT INTO wells (id, body, saved_at) VALUES (?, ?, ?) ON CONFLICT(id)"
                " DO UPDATE SET body = excluded.body, saved_at = excluded.saved_at",
                (well.id, body, _now()),
            )
        return Change.CREATED if row is None else Change.UPDATED

    async def delete(self, well_id: str) -> bool:
        """Remove a well and its readings; False when there was none."""
        async with self._lock:
            return await asyncio.to_thread(self._delete, well_id)

    def _delete(self, well_id: str) -> bool:
        with self._connect() as db, db:
            return db.execute("DELETE FROM wells WHERE id = ?", (well_id,)).rowcount > 0

    async def records(self) -> list[WellRecord]:
        """Every well with its readings, by name then id."""
        return await asyncio.to_thread(self._records)

    def _records(self) -> list[WellRecord]:
        with self._connect() as db:
            wells = [Well.model_validate_json(b) for (b,) in db.execute("SELECT body FROM wells")]
            readings: dict[str, list[WellReading]] = {}
            for (body,) in db.execute("SELECT body FROM readings ORDER BY measured_at, id"):
                reading = WellReading.model_validate_json(body)
                readings.setdefault(reading.well_id, []).append(reading)
        wells.sort(key=lambda w: (w.name.casefold(), w.id))
        return [WellRecord(well=w, readings=tuple(readings.get(w.id, ()))) for w in wells]

    # ── Readings ───────────────────────────────────────────────────────────────────────

    async def add_reading(self, reading: WellReading) -> Change:
        async with self._lock:
            return await asyncio.to_thread(self._add_reading, reading)

    def _add_reading(self, reading: WellReading) -> Change:
        with self._connect() as db, db:
            if (
                db.execute("SELECT 1 FROM wells WHERE id = ?", (reading.well_id,)).fetchone()
                is None
            ):
                raise WellsError(WellsFailure.UNKNOWN_WELL, f"no well {reading.well_id}")
            return _insert_reading(db, reading)

    # ── Import ─────────────────────────────────────────────────────────────────────────

    async def import_rows(
        self,
        rows: int,
        wells: Sequence[tuple[int, Well]],
        readings: Sequence[tuple[int, WellReading]],
    ) -> ImportReport:
        """Store an import's wells and readings in one transaction (``int``: the row)."""
        async with self._lock:
            return await asyncio.to_thread(self._import, rows, wells, readings)

    def _import(
        self,
        rows: int,
        wells: Sequence[tuple[int, Well]],
        readings: Sequence[tuple[int, WellReading]],
    ) -> ImportReport:
        well_changes = dict.fromkeys(Change, 0)
        reading_changes = dict.fromkeys(Change, 0)
        conflicts: set[int] = set()
        saved = _now()
        with self._connect() as db, db:
            for row, well in wells:
                body = well.model_dump_json()
                held = db.execute("SELECT body FROM wells WHERE id = ?", (well.id,)).fetchone()
                if held is None:
                    db.execute(
                        "INSERT INTO wells (id, body, saved_at) VALUES (?, ?, ?)",
                        (well.id, body, saved),
                    )
                    change = Change.CREATED
                else:
                    change = Change.UNCHANGED if held[0] == body else Change.CONFLICT
                well_changes[change] += 1
                if change is Change.CONFLICT:
                    conflicts.add(row)
            for row, reading in readings:
                change = _insert_reading(db, reading)
                reading_changes[change] += 1
                if change is Change.CONFLICT:
                    conflicts.add(row)
        return ImportReport(
            rows=rows,
            wells=well_changes,
            readings=reading_changes,
            conflict_rows=tuple(sorted(conflicts)),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _insert_reading(db: sqlite3.Connection, reading: WellReading) -> Change:
    body = reading.model_dump_json()
    inserted = db.execute(
        "INSERT INTO readings (id, well_id, measured_at, body, saved_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO NOTHING",
        (reading.id, reading.well_id, reading.measured_at.isoformat(), body, _now()),
    ).rowcount
    if inserted:
        return Change.CREATED
    (held,) = db.execute("SELECT body FROM readings WHERE id = ?", (reading.id,)).fetchone()
    return Change.UNCHANGED if held == body else Change.CONFLICT
