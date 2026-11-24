# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The release workflow's script, run against the repository on every change."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _script() -> ModuleType:
    path = ROOT / ".github" / "scripts" / "release_notes.py"
    spec = importlib.util.spec_from_file_location("release_notes", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_current_version_is_publishable_or_unreleased(tmp_path: Path) -> None:
    script = _script()
    notes = tmp_path / "notes.md"
    output = tmp_path / "github_output"
    args = ["--root", str(ROOT), "--notes-file", str(notes), "--github-output", str(output)]
    assert script.main(args) == 0
    if "publish=false" in output.read_text(encoding="utf-8"):
        assert script.project_version((ROOT / "pyproject.toml").read_text()) == "0.0.0"
    else:
        assert notes.read_text(encoding="utf-8").strip()


def test_version_zero_publishes_nothing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
    output = tmp_path / "github_output"
    args = ["--root", str(tmp_path), "--notes-file", str(tmp_path / "n.md")]
    assert _script().main([*args, "--github-output", str(output)]) == 0
    assert "publish=false" in output.read_text(encoding="utf-8")
    assert not (tmp_path / "n.md").exists()


def test_a_released_version_publishes_its_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [0.1.0] - 2026-01-01\n\n- x\n")
    output = tmp_path / "github_output"
    args = ["--root", str(tmp_path), "--notes-file", str(tmp_path / "n.md")]
    assert _script().main([*args, "--github-output", str(output)]) == 0
    assert "publish=true" in output.read_text(encoding="utf-8")
    assert "tag=v0.1.0" in output.read_text(encoding="utf-8")
    assert (tmp_path / "n.md").read_text(encoding="utf-8") == "- x\n"


def test_a_released_version_without_a_section_fails(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.2.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
    assert _script().main(["--root", str(tmp_path), "--notes-file", str(tmp_path / "n.md")]) == 1


def test_a_version_without_a_section_fails() -> None:
    script = _script()
    with pytest.raises(script.ReleaseError):
        script.changelog_section("# Changelog\n\n## [0.1.0] - 2026-01-01\n\n- x\n", "0.2.0")


def test_versions_below_one_are_prereleases() -> None:
    script = _script()
    assert script.is_prerelease("0.9.0")
    assert not script.is_prerelease("1.0.0")
