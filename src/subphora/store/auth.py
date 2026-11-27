# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The users and their sessions: one SQLite database (``data/auth/``, git-ignored).

A session is kept by the SHA-256 of its token, never the token itself, so a copy of the
database (a backup) cannot be used to sign in. A user's removal removes their sessions.
SQLite's calls block, so the service runs each in a worker thread.
"""

import contextlib
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from subphora.domain.auth import AuthError, AuthFailure

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    name TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS sessions (
    token_sha256 TEXT PRIMARY KEY,
    name TEXT NOT NULL REFERENCES users(name) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
) STRICT;
"""


class AuthStore:
    def __init__(self, database: Path, busy_timeout_s: float) -> None:
        self._database = database
        self._timeout = busy_timeout_s

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            self._database.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._database, timeout=self._timeout)
        except (OSError, sqlite3.Error) as exc:
            raise AuthError(AuthFailure.STORE_UNAVAILABLE, "the users cannot be read") from exc
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(_SCHEMA)
            with connection:
                yield connection
        except sqlite3.Error as exc:
            raise AuthError(AuthFailure.STORE_UNAVAILABLE, "the users store failed") from exc
        finally:
            connection.close()

    def add_user(self, name: str, password_hash: str, now: datetime) -> None:
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO users (name, password_hash, created_at) VALUES (?, ?, ?)",
                    (name, password_hash, now.isoformat(timespec="microseconds")),
                )
            except sqlite3.IntegrityError:
                raise AuthError(AuthFailure.USER_EXISTS, "that user exists already") from None

    def set_password(self, name: str, password_hash: str) -> None:
        """A new password; the user's sessions end, so every device signs in again."""
        with self._connect() as db:
            changed = db.execute(
                "UPDATE users SET password_hash = ? WHERE name = ?", (password_hash, name)
            ).rowcount
            if not changed:
                raise AuthError(AuthFailure.UNKNOWN_USER, "no such user")
            db.execute("DELETE FROM sessions WHERE name = ?", (name,))

    def remove_user(self, name: str) -> None:
        with self._connect() as db:
            if not db.execute("DELETE FROM users WHERE name = ?", (name,)).rowcount:
                raise AuthError(AuthFailure.UNKNOWN_USER, "no such user")

    def users(self) -> list[str]:
        with self._connect() as db:
            return [row[0] for row in db.execute("SELECT name FROM users ORDER BY name")]

    def password_hash(self, name: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE name = ?", (name,)).fetchone()
        return None if row is None else str(row[0])

    def add_session(
        self, token_sha256: str, name: str, now: datetime, expires_at: datetime
    ) -> None:
        with self._connect() as db:
            # Sessions that ended are dropped whenever one begins.
            db.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (now.isoformat(timespec="microseconds"),),
            )
            db.execute(
                "INSERT INTO sessions (token_sha256, name, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    token_sha256,
                    name,
                    now.isoformat(timespec="microseconds"),
                    expires_at.isoformat(timespec="microseconds"),
                ),
            )

    def session_user(self, token_sha256: str, now: datetime) -> str | None:
        """The user of a session that has not ended, else None."""
        with self._connect() as db:
            row = db.execute(
                "SELECT name FROM sessions WHERE token_sha256 = ? AND expires_at > ?",
                (token_sha256, now.isoformat(timespec="microseconds")),
            ).fetchone()
        return None if row is None else str(row[0])

    def end_session(self, token_sha256: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_sha256 = ?", (token_sha256,))
