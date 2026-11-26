# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Field mode's use cases (MASTER_PLAN §4.7): the outbox's records and files, checked
against the settings before the store keeps them.

The browser sends records in batches and each file apart, after its record. A record the
settings refuse fails its whole batch, so the browser keeps it and says why; a file must
match, byte for byte, the type, size and SHA-256 its record declared.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from subphora.config import Settings
from subphora.domain.field import (
    MEDIA_FAMILIES,
    FieldError,
    FieldFailure,
    FieldSummary,
    Observation,
    Outcome,
    SyncResult,
)
from subphora.store.field import FieldStore


def media_type(content_type: str) -> str:
    """The type without its parameters (``audio/webm;codecs=opus`` is ``audio/webm``)."""
    return content_type.split(";")[0].strip().lower()


class FieldService:
    def __init__(self, settings: Settings, root: Path) -> None:
        self._settings = settings.field
        store = self._settings.store
        self._store = FieldStore(
            store.database_path(root), store.media_path(root), store.busy_timeout_s
        )

    async def sync(self, observations: Sequence[Observation]) -> tuple[SyncResult, ...]:
        field = self._settings
        if len(observations) > field.sync.batch_size:
            raise FieldError(
                FieldFailure.TOO_MANY, f"at most {field.sync.batch_size} records a request"
            )
        for observation in observations:
            if observation.text is not None and len(observation.text) > field.note_max_chars:
                raise FieldError(
                    FieldFailure.NOTE_TOO_LONG,
                    f"{observation.id}: a text has at most {field.note_max_chars} characters",
                )
            media = observation.media
            if media is not None:
                self._check_type(observation.id, media.content_type)
                if media.size_bytes > field.media.max_bytes:
                    raise FieldError(
                        FieldFailure.MEDIA_TOO_LARGE,
                        f"{observation.id}: a file has at most {field.media.max_bytes} bytes",
                    )
        return await self._store.upsert(observations)

    def _check_type(self, observation_id: str, content_type: str) -> str:
        extension = self._settings.media.types.get(content_type)
        if extension is None:
            raise FieldError(
                FieldFailure.MEDIA_TYPE, f"{observation_id}: {content_type} is not accepted"
            )
        return extension

    async def media(self, observation_id: str, content_type: str, content: bytes) -> Outcome:
        """Store a record's file once its record is stored and the bytes match it."""
        if len(content) > self._settings.media.max_bytes:
            raise FieldError(FieldFailure.MEDIA_TOO_LARGE, "the file is too large")
        observation = await self._store.observation(observation_id)
        if observation is None:
            raise FieldError(
                FieldFailure.UNKNOWN_OBSERVATION, f"no record {observation_id}; send it first"
            )
        declared = observation.media
        if declared is None or observation.kind not in MEDIA_FAMILIES:
            raise FieldError(FieldFailure.NO_MEDIA, f"a {observation.kind} has no file")
        sent_type = media_type(content_type)
        if sent_type != declared.content_type:
            raise FieldError(
                FieldFailure.MEDIA_TYPE,
                f"the record declared {declared.content_type}, the file is {sent_type}",
            )
        extension = self._check_type(observation_id, sent_type)
        if len(content) != declared.size_bytes or (
            hashlib.sha256(content).hexdigest() != declared.sha256
        ):
            raise FieldError(
                FieldFailure.MEDIA_MISMATCH, "the file is not the one its record declared"
            )
        return await self._store.put_media(observation_id, declared, extension, content)

    async def summary(self) -> FieldSummary:
        return await self._store.summary()
