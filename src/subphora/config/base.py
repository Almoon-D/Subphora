# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The base of every settings section: frozen and closed to unknown keys."""

from pydantic import BaseModel, ConfigDict


class Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
