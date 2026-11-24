# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/api.yaml`` and ``config/defaults/store.yaml``."""

from pathlib import Path

from pydantic import Field

from subphora.config.base import Section

_PORT = Field(ge=1, le=65535)


class ApiSettings(Section):
    host: str = Field(min_length=1)
    port: int = _PORT
    dev_web_port: int = _PORT


class StoreSettings(Section):
    # Relative to the repository root unless absolute.
    cache_dir: Path

    def cache_path(self, root: Path) -> Path:
        return self.cache_dir if self.cache_dir.is_absolute() else root / self.cache_dir
