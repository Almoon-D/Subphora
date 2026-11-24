# Copyright (c) 2026 Almoon-D. All rights reserved.
"""`subphora sources check` and `subphora sources list`, with HTTP mocked."""

import httpx
import pytest
import respx

from subphora.__main__ import main
from subphora.config import Settings, load_settings
from tests.support import fixture_bytes

PNOA_WMTS = "https://www.ign.es/wmts/pnoa-ma"


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real catalogue, without the waits between retries."""
    real = load_settings()
    client = real.sources.client.model_copy(update={"retry_backoff_s": 0})
    sources = real.sources.model_copy(update={"client": client})

    def fast() -> Settings:
        return real.model_copy(update={"sources": sources})

    monkeypatch.setattr("subphora.__main__.load_settings", fast)


def test_list_prints_every_service(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sources", "list"]) == 0
    out = capsys.readouterr().out
    for entry in load_settings().sources.services:  # the real one, unpatched here
        assert entry.id in out
    assert "never cached" in out  # Google
    assert "key from $GOOGLE_MAPS_API_KEY" in out


def test_check_of_an_unknown_id_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sources", "check", "--only", "nope"]) == 2
    assert "unknown service id: nope" in capsys.readouterr().out


def test_check_without_a_subcommand_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["sources"])
    assert exit_info.value.code == 2


def test_check_passes_when_every_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    headers = {"content-type": "text/xml", "access-control-allow-origin": "*"}
    with respx.mock as mock:
        mock.get(PNOA_WMTS, params={"request": "GetTile"}).respond(
            200, content=b"\xff\xd8jpeg", headers={**headers, "content-type": "image/jpeg"}
        )
        mock.get(PNOA_WMTS).respond(
            200, content=fixture_bytes("ign_pnoa_wmts_capabilities.xml"), headers=headers
        )
        assert main(["sources", "check", "--only", "ign-pnoa-wmts"]) == 0
    out = capsys.readouterr().out
    assert "ign-pnoa-wmts" in out
    assert out.strip().endswith("4 ok, 0 failed, 0 not checked")


def test_check_fails_when_a_service_is_unreachable(capsys: pytest.CaptureFixture[str]) -> None:
    with respx.mock as mock:
        mock.get(PNOA_WMTS).mock(side_effect=httpx.ConnectError("refused"))
        assert main(["sources", "check", "--only", "ign-pnoa-wmts"]) == 1
    assert "could not connect" in capsys.readouterr().out


def test_a_service_needing_a_key_does_not_fail_the_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with respx.mock(assert_all_called=False):
        assert main(["sources", "check", "--only", "google-map-tiles"]) == 0
    assert "not checked" in capsys.readouterr().out
