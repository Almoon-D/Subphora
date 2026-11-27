# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Backups of the private data (MASTER_PLAN §4.9): what an archive holds and how it is
checked."""

from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, Field

from subphora.domain import DomainModel


class BackupFailure(StrEnum):
    NO_SOURCE = "no_source"
    DESTINATION_INSIDE_SOURCE = "destination_inside_source"
    UNREADABLE = "unreadable"
    NO_MANIFEST = "no_manifest"
    UNSAFE_PATH = "unsafe_path"
    MISSING_FILE = "missing_file"
    UNLISTED_FILE = "unlisted_file"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DATABASE_DAMAGED = "database_damaged"


class BackupError(Exception):
    def __init__(self, failure: BackupFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail


class BackupEntry(DomainModel):
    """One file of the archive, by its path relative to the backed-up folder."""

    path: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database: bool


class BackupManifest(DomainModel):
    """``manifest.json`` at the root of every archive."""

    created_at: AwareDatetime
    version: str
    excluded: tuple[str, ...]
    files: tuple[BackupEntry, ...]


class BackupSummary(DomainModel):
    """An archive written or checked: its file name, when, and what it holds."""

    archive: str
    created_at: datetime
    files: int
    databases: int
    size_bytes: int
