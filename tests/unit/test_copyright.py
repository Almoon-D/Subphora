# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Every tracked file that can hold a comment carries the copyright notice (decision 0011).

The notice is `[tool.subphora] copyright_notice` in pyproject.toml. It must appear within the
first or last lines of each file (a shebang or an encoding line may come before it).
"""

import fnmatch
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EDGE_LINES = 3

# Files that cannot hold a comment, are generated, or are third-party data.
EXEMPT = (
    "*.json",
    "*.webmanifest",
    "*.lock",
    "*.gitkeep",
    "*/py.typed",
    "tests/fixtures/*",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.webp",
    "*.pdf",
    "*.woff",
    "*.woff2",
)


def notice() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    value = data["tool"]["subphora"]["copyright_notice"]
    assert isinstance(value, str)
    return value


def is_exempt(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in EXEMPT)


def carries_notice(text: str, expected: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return any(expected in line for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:])


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if line and (ROOT / line).is_file()]


def test_every_file_carries_the_notice() -> None:
    expected = notice()
    missing = [
        path
        for path in tracked_files()
        if not is_exempt(path)
        and not carries_notice((ROOT / path).read_text(encoding="utf-8"), expected)
    ]
    assert missing == [], f"files without the copyright notice: {missing}"


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("# Copyright (c) 2026 Almoon-D. All rights reserved.\ncode\n", True),
        ("#!/bin/sh\n# Copyright (c) 2026 Almoon-D. All rights reserved.\n", True),
        ("a\nb\nc\nd\nCopyright (c) 2026 Almoon-D. All rights reserved.\n", True),
        ("a\nb\nc\nCopyright (c) 2026 Almoon-D. All rights reserved.\nd\ne\nf\ng\n", False),
        ("Copyright (c) 1999 Almoon-D. All rights reserved.\n", False),
        ("", False),
    ],
)
def test_the_notice_must_sit_at_an_edge(text: str, found: bool) -> None:
    assert carries_notice(text, "Copyright (c) 2026 Almoon-D. All rights reserved.") is found


@pytest.mark.parametrize(
    ("path", "exempt"),
    [
        ("package.json", True),
        ("uv.lock", True),
        ("tests/fixtures/catastro/wfs.xml", True),
        ("src/subphora/py.typed", True),
        ("src/subphora/__init__.py", False),
        ("web/src/main.ts", False),
    ],
)
def test_the_exemption_list(path: str, exempt: bool) -> None:
    assert is_exempt(path) is exempt
