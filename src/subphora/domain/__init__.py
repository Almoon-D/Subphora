# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Domain models: frozen, strict, importing nothing else of ours (import-linter contract)."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base for every domain model: immutable and closed to unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")
