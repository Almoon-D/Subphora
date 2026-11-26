# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Field observations (MASTER_PLAN §4.7): append-only records made on site.

Each record has a UUIDv7 id made by the device, the UTC time it was recorded, the device's
position with its reported accuracy (or none, said explicitly), the spot the user was
guided to (if any), and its kind's content: a note's text, a photo's or a voice memo's
file (declared by type, size and SHA-256, the bytes sent apart), or a track point. A
record never changes: the server keeps the first copy of an id and reports a different
one under the same id as a conflict.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from subphora.domain import DomainModel

_SHA256 = r"^[0-9a-f]{64}$"
_MEDIA_TYPE = r"^(image|audio)/[a-z0-9.+-]+$"
_AREA_ID = r"^[0-9a-f]{16}$"


def _uuid7(value: str) -> str:
    """The id in its canonical form, or an error unless it is a UUID of version 7."""
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("not a UUID") from exc
    if parsed.version != 7 or parsed.variant != uuid.RFC_4122:
        raise ValueError("not a UUIDv7")
    canonical = str(parsed)
    if canonical != value:
        raise ValueError("a UUID is written in lower case with hyphens")
    return canonical


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


class ObservationKind(StrEnum):
    """What a record holds. An instrument reading would be a new kind (§4.8); none exists
    before session 16."""

    NOTE = "note"
    PHOTO = "photo"
    VOICE = "voice"
    TRACK_POINT = "track_point"


# The kinds that carry a file, and the media family of each.
MEDIA_FAMILIES = {ObservationKind.PHOTO: "image", ObservationKind.VOICE: "audio"}


class Fix(DomainModel):
    """A position as the device's Geolocation API reported it."""

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    # The radius, in metres, within which the device says the position lies (95 %).
    accuracy_m: float = Field(gt=0)
    altitude_m: float | None = None
    altitude_accuracy_m: float | None = Field(default=None, gt=0)
    # Degrees clockwise from true north while moving; None when the device gives none.
    heading_deg: float | None = Field(default=None, ge=0, lt=360)
    speed_m_s: float | None = Field(default=None, ge=0)
    fixed_at: AwareDatetime

    _fixed_utc = field_validator("fixed_at")(_utc)


class Target(DomainModel):
    """The candidate spot the user was guided to: its detailed map's id and its rank."""

    area_id: str = Field(pattern=_AREA_ID)
    rank: int = Field(ge=1)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class Media(DomainModel):
    """A photo's or a voice memo's file, as the device declared it."""

    content_type: str = Field(pattern=_MEDIA_TYPE)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=_SHA256)


class Observation(DomainModel):
    id: str
    kind: ObservationKind
    recorded_at: AwareDatetime
    # None: the device had no position when it was recorded.
    position: Fix | None
    target: Target | None
    # A note's text, or a photo's or voice memo's caption.
    text: str | None = None
    media: Media | None = None
    # The track a track point belongs to: the UUIDv7 of the walk it was recorded on.
    track_id: str | None = None

    _id_v7 = field_validator("id")(_uuid7)
    _recorded_utc = field_validator("recorded_at")(_utc)

    @field_validator("track_id")
    @classmethod
    def _track_v7(cls, value: str | None) -> str | None:
        return None if value is None else _uuid7(value)

    @model_validator(mode="after")
    def _content_fits_kind(self) -> Self:
        kind = self.kind
        if kind is ObservationKind.NOTE and not (self.text and self.text.strip()):
            raise ValueError("a note has text")
        if kind in MEDIA_FAMILIES:
            if self.media is None:
                raise ValueError(f"a {kind} declares its file")
            if self.media.content_type.split("/")[0] != MEDIA_FAMILIES[kind]:
                raise ValueError(f"a {kind} is an {MEDIA_FAMILIES[kind]}/ file")
        elif self.media is not None:
            raise ValueError(f"a {kind} has no file")
        if kind is ObservationKind.TRACK_POINT:
            if self.position is None or self.track_id is None:
                raise ValueError("a track point has a position and a track")
            if self.text is not None:
                raise ValueError("a track point has no text")
        elif self.track_id is not None:
            raise ValueError(f"a {kind} belongs to no track")
        return self


class Outcome(StrEnum):
    """What the server made of a record it was sent."""

    # Stored now.
    CREATED = "created"
    # Already stored, identical: a retried sync.
    DUPLICATE = "duplicate"
    # Already stored with different content under this id: nothing is overwritten.
    CONFLICT = "conflict"


class SyncResult(DomainModel):
    id: str
    outcome: Outcome


class SyncAnswer(DomainModel):
    """The answer to a batch: one result per record sent, in its order."""

    results: tuple[SyncResult, ...]


class MediaAnswer(DomainModel):
    id: str
    outcome: Outcome


class KindCount(DomainModel):
    kind: ObservationKind
    records: int
    # Of the records of a media kind, how many have their file stored.
    with_media: int


class FieldSummary(DomainModel):
    """What the server's store holds, for ``subphora field summary``."""

    kinds: tuple[KindCount, ...]
    tracks: int
    first_recorded_at: datetime | None
    last_recorded_at: datetime | None


class FieldFailure(StrEnum):
    INVALID_OBSERVATION = "invalid_observation"
    TOO_MANY = "too_many"
    NOTE_TOO_LONG = "note_too_long"
    UNKNOWN_OBSERVATION = "unknown_observation"
    NO_MEDIA = "no_media"
    MEDIA_TYPE = "media_type"
    MEDIA_TOO_LARGE = "media_too_large"
    MEDIA_MISMATCH = "media_mismatch"
    STORE_UNAVAILABLE = "store_unavailable"


class FieldError(Exception):
    """A field request refused or failed; ``detail`` never carries a record's content."""

    def __init__(self, failure: FieldFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
