# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The imported piezometric levels on disk: one JSON file (git-ignored ``data/``), written
to a temporary name and renamed into place. The functions block."""

from pathlib import Path

from subphora.domain.piezometry import PiezometryDataset
from subphora.store.national import write_json


def write_piezometry(path: Path, dataset: PiezometryDataset) -> None:
    write_json(path, dataset)


def read_piezometry(path: Path) -> PiezometryDataset | None:
    """The imported levels, or None before the first import; raises ValueError when the
    file cannot be read (written by another version: import again)."""
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        return PiezometryDataset.model_validate_json(content)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}; run `subphora piezometry import` again") from exc
