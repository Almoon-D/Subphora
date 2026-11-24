from pathlib import Path

import pytest

from subphora import __version__
from subphora.__main__ import main
from subphora.config import load_settings
from subphora.domain import DomainModel


def test_version_is_semver() -> None:
    assert len(__version__.split(".")) == 3


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_config_prints_settings(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config"]) == 0
    assert '"log_level"' in capsys.readouterr().out


def test_cli_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out


def test_owner_overrides_defaults(tmp_path: Path) -> None:
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults" / "core.yaml").write_text("log_level: INFO\n")
    (tmp_path / "owner.yaml").write_text("core:\n  log_level: DEBUG\n")
    assert load_settings(tmp_path).core.log_level == "DEBUG"


def test_an_invalid_log_level_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults" / "core.yaml").write_text("log_level: LOUD\n")
    with pytest.raises(ValueError, match="log_level"):
        load_settings(tmp_path)


def test_unknown_key_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults" / "core.yaml").write_text("log_level: INFO\ntypo: 1\n")
    with pytest.raises(ValueError, match="typo"):
        load_settings(tmp_path)


def test_a_file_that_is_not_a_mapping_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults" / "core.yaml").write_text("- a list\n")
    with pytest.raises(ValueError, match="mapping"):
        load_settings(tmp_path)


def test_domain_models_are_frozen_and_closed() -> None:
    class Thing(DomainModel):
        name: str

    thing = Thing(name="a")
    with pytest.raises(ValueError, match="frozen"):
        thing.name = "b"
    with pytest.raises(ValueError, match="extra"):
        Thing.model_validate({"name": "a", "other": 1})
