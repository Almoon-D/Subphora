# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Backups of the private data (MASTER_PLAN §4.9): one archive written and read back
(the restore test) per run, the oldest pruned only after the new one passes, and the
nightly schedule in local time."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from subphora import __version__
from subphora.config import Settings
from subphora.domain.backup import BackupError, BackupSummary
from subphora.store.backup import create_backup, prune, restore_backup, verify_backup

_log = logging.getLogger(__name__)


def next_run(now: datetime, settings: Settings) -> datetime:
    """The next nightly time after ``now``, in UTC. A local time that a clock change skips
    or repeats is resolved by ``zoneinfo`` (the first occurrence)."""
    nightly = settings.backup.nightly
    local = now.astimezone(nightly.zone)
    candidate = local.replace(
        hour=nightly.at.hour, minute=nightly.at.minute, second=0, microsecond=0
    )
    if candidate <= local:
        candidate = (local + timedelta(days=1)).replace(
            hour=nightly.at.hour, minute=nightly.at.minute, second=0, microsecond=0
        )
    return candidate.astimezone(UTC)


class BackupService:
    def __init__(
        self,
        settings: Settings,
        root: Path,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._backup = settings.backup
        self._source = self._backup.source_path(root)
        self._destination = self._backup.destination_path(root)
        self._clock = clock

    @property
    def destination(self) -> Path:
        return self._destination

    def run(self) -> tuple[BackupSummary, list[str]]:
        """Write an archive, read it back, then prune; the summary and the pruned names."""
        written = create_backup(
            self._source, self._destination, self._backup.exclude, self._clock(), __version__
        )
        checked = verify_backup(self._destination / written.archive)
        return checked, prune(self._destination, self._backup.keep)

    def verify(self, archive: Path) -> BackupSummary:
        return verify_backup(archive)

    def restore(self, archive: Path) -> Path | None:
        return restore_backup(archive, self._source, self._clock())

    async def nightly(self, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        """Run every night at the configured time, for ever; a failed night is logged and
        the next one still runs."""
        while True:
            now = self._clock()
            wait = (next_run(now, self._settings) - now).total_seconds()
            _log.info("next backup in %.0f s", wait)
            await sleep(wait)
            try:
                summary, pruned = await asyncio.to_thread(self.run)
            except BackupError as exc:
                _log.error("the nightly backup failed (%s): %s", exc.failure.value, exc.detail)
                continue
            _log.info(
                "backup %s: %d files, %d databases, %d bytes, verified; %d old ones deleted",
                summary.archive,
                summary.files,
                summary.databases,
                summary.size_bytes,
                len(pruned),
            )
