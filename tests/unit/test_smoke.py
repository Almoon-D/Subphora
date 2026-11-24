# Copyright (c) 2026 Almoon-D. All rights reserved.
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


def test_owner_overrides_defaults(config_dir: Path) -> None:
    (config_dir / "owner.yaml").write_text("core:\n  log_level: DEBUG\n")
    assert load_settings(config_dir).core.log_level == "DEBUG"


def test_an_invalid_log_level_is_an_error(config_dir: Path) -> None:
    (config_dir / "defaults" / "core.yaml").write_text("log_level: LOUD\n")
    with pytest.raises(ValueError, match="log_level"):
        load_settings(config_dir)


def test_unknown_key_is_an_error(config_dir: Path) -> None:
    (config_dir / "defaults" / "core.yaml").write_text("log_level: INFO\ntypo: 1\n")
    with pytest.raises(ValueError, match="typo"):
        load_settings(config_dir)


def test_a_file_that_is_not_a_mapping_is_an_error(config_dir: Path) -> None:
    (config_dir / "defaults" / "core.yaml").write_text("- a list\n")
    with pytest.raises(ValueError, match="mapping"):
        load_settings(config_dir)


def test_domain_models_are_frozen_and_closed() -> None:
    class Thing(DomainModel):
        name: str

    thing = Thing(name="a")
    with pytest.raises(ValueError, match="frozen"):
        thing.name = "b"
    with pytest.raises(ValueError, match="extra"):
        Thing.model_validate({"name": "a", "other": 1})


@pytest.mark.parametrize(
    ("key", "printed"),
    [("api.port", "8000"), ("api.host", "127.0.0.1"), ("map.cadastre.style", "")],
)
def test_cli_config_prints_one_key(
    capsys: pytest.CaptureFixture[str], key: str, printed: str
) -> None:
    assert main(["config", key]) == 0
    assert capsys.readouterr().out == printed + "\n"


def test_cli_config_prints_a_section_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config", "map.initial_view"]) == 0
    assert '"zoom": 5' in capsys.readouterr().out


@pytest.mark.parametrize("key", ["nope", "api.nope", "api.port.deeper"])
def test_cli_config_of_an_unknown_key_is_a_usage_error(
    capsys: pytest.CaptureFixture[str], key: str
) -> None:
    assert main(["config", key]) == 2
    assert "unknown configuration key" in capsys.readouterr().out


def test_cli_serve_runs_the_app_without_an_access_log(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def run(app: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("uvicorn.run", run)
    assert main(["serve"]) == 0
    (call,) = calls
    assert call["host"] == "127.0.0.1"
    assert call["port"] == 8000
    assert call["access_log"] is False
