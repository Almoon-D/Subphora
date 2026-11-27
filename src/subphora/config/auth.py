# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/auth.yaml``: the login (MASTER_PLAN §4.9)."""

from pathlib import Path
from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section


class CookieSettings(Section):
    name: str = Field(pattern=r"^[A-Za-z0-9_]{1,64}$")
    lifetime_days: PositiveInt


class ScryptSettings(Section):
    n: int = Field(ge=2)
    r: PositiveInt
    p: PositiveInt
    max_memory_mb: PositiveInt

    @model_validator(mode="after")
    def _cost_fits(self) -> Self:
        if self.n & (self.n - 1):
            raise ValueError("auth.password.scrypt.n must be a power of two")
        if 128 * self.n * self.r > self.max_memory_mb * 1024 * 1024:
            raise ValueError("auth.password.scrypt: n and r need more than max_memory_mb")
        return self


class PasswordSettings(Section):
    min_length: int = Field(ge=8)
    max_length: PositiveInt
    scrypt: ScryptSettings
    salt_bytes: int = Field(ge=16)
    key_bytes: int = Field(ge=32)

    @model_validator(mode="after")
    def _lengths_ordered(self) -> Self:
        if self.max_length < self.min_length:
            raise ValueError("auth.password.max_length is below min_length")
        return self


class LockoutSettings(Section):
    max_failures: PositiveInt
    window_s: PositiveFloat


class AuthSettings(Section):
    # Relative to the repository root unless absolute.
    database: Path
    busy_timeout_s: PositiveFloat
    cookie: CookieSettings
    password: PasswordSettings
    lockout: LockoutSettings

    def database_path(self, root: Path) -> Path:
        return self.database if self.database.is_absolute() else root / self.database
