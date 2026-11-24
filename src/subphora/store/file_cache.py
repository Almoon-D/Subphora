# Copyright (c) 2026 Almoon-D. All rights reserved.
"""A file cache of upstream responses, one directory per catalogued service.

Each entry is the response body and a small JSON sidecar with the time it was fetched.
The lifetime comes from the source catalogue; a lifetime of 0 means never cache (a service
whose terms forbid storing its data), so such entries are neither read nor written. Writes
are atomic (a temporary file renamed into place), so a crash never leaves a half-written
entry. The methods block: async callers run them in a thread.
"""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

type Clock = Callable[[], datetime]

_NAMESPACE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class CachedEntry:
    content: bytes
    fetched_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


class FileCache:
    def __init__(self, root: Path, clock: Clock = utc_now) -> None:
        self._root = root
        self._clock = clock

    def _paths(self, namespace: str, key: str) -> tuple[Path, Path]:
        if not _NAMESPACE.match(namespace):
            raise ValueError(f"cache namespace {namespace!r} must be a catalogue service id")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        folder = self._root / namespace
        return folder / f"{digest}.bin", folder / f"{digest}.json"

    def get(self, namespace: str, key: str, lifetime_s: int) -> CachedEntry | None:
        """The entry if it exists and is younger than ``lifetime_s``; else None."""
        if lifetime_s <= 0:
            return None
        body, meta = self._paths(namespace, key)
        try:
            fetched_at = datetime.fromisoformat(json.loads(meta.read_text("utf-8"))["fetched_at"])
            content = body.read_bytes()
        except OSError, ValueError, KeyError, TypeError:
            # Missing, unreadable or corrupt: a miss, and the next put replaces it.
            return None
        if fetched_at.tzinfo is None:
            return None
        age = self._clock() - fetched_at
        if age < timedelta(0) or age >= timedelta(seconds=lifetime_s):
            return None
        return CachedEntry(content=content, fetched_at=fetched_at)

    def put(
        self, namespace: str, key: str, content: bytes, fetched_at: datetime, lifetime_s: int
    ) -> None:
        """Store an entry, unless the service may never be cached (lifetime 0)."""
        if lifetime_s <= 0:
            return
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        body, meta = self._paths(namespace, key)
        body.parent.mkdir(parents=True, exist_ok=True)
        _write_atomic(body, content)
        _write_atomic(meta, json.dumps({"fetched_at": fetched_at.isoformat()}).encode("utf-8"))


def _write_atomic(path: Path, content: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
