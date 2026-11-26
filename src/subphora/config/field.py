# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/field.yaml``: field mode (MASTER_PLAN §4.7)."""

import re
from pathlib import Path
from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section

# A media type without parameters, in the photo or voice families.
_MEDIA_TYPE = r"^(image|audio)/[a-z0-9.+-]+$"


class GeolocationSettings(Section):
    high_accuracy: bool
    timeout_ms: PositiveInt
    maximum_age_ms: int = Field(ge=0)


class TrackSettings(Section):
    min_interval_s: PositiveFloat
    min_distance_m: float = Field(ge=0)


class SyncSettings(Section):
    batch_size: int = Field(ge=1, le=500)
    retry_s: PositiveFloat


class MediaSettings(Section):
    max_bytes: PositiveInt
    # Content type -> the extension of its file in the store.
    types: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _types_well_formed(self) -> Self:
        for content_type, extension in self.types.items():
            if not re.fullmatch(_MEDIA_TYPE, content_type):
                raise ValueError(f"field.media.types: {content_type!r} is not a media type")
            if not re.fullmatch(r"[a-z0-9]{1,8}", extension):
                raise ValueError(f"field.media.types: {extension!r} is not an extension")
        families = {content_type.split("/")[0] for content_type in self.types}
        if families != {"image", "audio"}:
            raise ValueError("field.media.types: photos (image/) and voice memos (audio/) both")
        return self


class FieldStoreSettings(Section):
    # Relative to the repository root unless absolute.
    database: Path
    media_dir: Path
    busy_timeout_s: PositiveFloat

    def database_path(self, root: Path) -> Path:
        return self.database if self.database.is_absolute() else root / self.database

    def media_path(self, root: Path) -> Path:
        return self.media_dir if self.media_dir.is_absolute() else root / self.media_dir


class FieldSettings(Section):
    at_spot_m: PositiveFloat
    note_max_chars: PositiveInt
    geolocation: GeolocationSettings
    track: TrackSettings
    sync: SyncSettings
    media: MediaSettings
    store: FieldStoreSettings
