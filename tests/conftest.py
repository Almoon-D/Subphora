# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Fixtures shared by every test; plain helpers live in tests/support.py."""

from pathlib import Path

import pytest

from tests.support import copy_config


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A copy of the real config/ to edit in a test."""
    return copy_config(tmp_path)
