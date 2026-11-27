# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The login (MASTER_PLAN §4.9): every route behind a session, the cookie's flags, each
way a login is refused (wrong password, unknown name, lockout, a malformed body, a store
that fails), sessions that end, and ``subphora users``. Names and passwords are synthetic."""

import io
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

import subphora.__main__ as cli
import subphora.config
from subphora.api import create_app
from subphora.api.auth import session_token
from subphora.config import Settings
from subphora.config.auth import AuthSettings
from subphora.domain.auth import AuthError, AuthFailure
from subphora.services.auth import AuthService, hash_password, verify_password
from subphora.store.auth import AuthStore
from tests.support import fast_settings, signed_in

PASSWORD = "correct horse battery"


def cheap(settings: Settings) -> Settings:
    """The real settings with scrypt's cost lowered, so a test hashes in microseconds."""
    auth = settings.auth
    scrypt = auth.password.scrypt.model_copy(update={"n": 16, "r": 1})
    password = auth.password.model_copy(update={"scrypt": scrypt})
    return settings.model_copy(update={"auth": auth.model_copy(update={"password": password})})


@pytest.fixture
def settings() -> Settings:
    return cheap(fast_settings())


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"the login asked the network: {request.url.host}")


@asynccontextmanager
async def serve(settings: Settings, root: Path) -> AsyncIterator[httpx.AsyncClient]:
    """The API with no session: the client is what an unknown browser is."""
    app = create_app(
        settings,
        root=root,
        transport=httpx.MockTransport(_no_network),
        executor=ThreadPoolExecutor(max_workers=1),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            yield client


async def add_user(settings: Settings, root: Path, name: str = "ana") -> None:
    await AuthService(settings, root).add_user(name, PASSWORD)


async def login(client: httpx.AsyncClient, name: str, password: str) -> httpx.Response:
    return await client.post("/api/auth/login", json={"name": name, "password": password})


# ── Every route needs a session ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/map"),
        ("GET", "/api/search?q=Daimiel"),
        ("GET", "/api/national"),
        ("POST", "/api/parcel"),
        ("GET", "/api/parcel/0123456789abcdef/report.pdf"),
        ("POST", "/api/field/observations"),
        ("PUT", "/api/field/observations/x/media"),
        ("GET", "/api/auth/me"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
        ("GET", "/api/no-such-route"),
    ],
)
async def test_every_route_but_the_login_refuses_a_request_without_a_session(
    settings: Settings, tmp_path: Path, method: str, path: str
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await client.request(method, path)
    assert answer.status_code == 401
    assert answer.json()["code"] == "unauthenticated"
    assert answer.headers["cache-control"] == "no-store"


async def test_the_health_check_answers_without_a_session(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await client.get("/api/health")
    assert answer.status_code == 200
    assert answer.json() == {"status": "ok"}


async def test_a_forged_or_unknown_session_is_refused(settings: Settings, tmp_path: Path) -> None:
    await add_user(settings, tmp_path)
    async with serve(settings, tmp_path) as client:
        for cookie in ("subphora_session=forged", "subphora_session=", "other=1", "bad;;=="):
            answer = await client.get("/api/auth/me", headers={"Cookie": cookie})
            assert answer.status_code == 401, cookie


# ── The login ─────────────────────────────────────────────────────────────────────────


async def test_a_login_sets_a_secure_cookie_that_opens_every_route(
    settings: Settings, tmp_path: Path
) -> None:
    await add_user(settings, tmp_path)
    async with serve(settings, tmp_path) as client:
        answer = await login(client, " Ana ", PASSWORD)
        assert answer.status_code == 200
        assert answer.json() == {"name": "ana"}
        cookie = answer.headers["set-cookie"]
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=7776000"):
            assert flag.lower() in cookie.lower(), flag
        assert (await client.get("/api/auth/me")).json() == {"name": "ana"}
        assert (await client.get("/api/map")).status_code == 200


async def test_logout_ends_the_session_on_the_server(settings: Settings, tmp_path: Path) -> None:
    await add_user(settings, tmp_path)
    async with serve(settings, tmp_path) as client:
        await login(client, "ana", PASSWORD)
        token = client.cookies["subphora_session"]
        answer = await client.post("/api/auth/logout")
        assert answer.status_code == 204
        assert 'subphora_session=""' in answer.headers["set-cookie"]
        # The old token no longer works, even if a copy of the cookie was kept.
        again = await client.get("/api/auth/me", headers={"Cookie": f"subphora_session={token}"})
        assert again.status_code == 401


@pytest.mark.parametrize(
    ("name", "password"),
    [
        ("ana", "wrong password here"),
        ("nobody", PASSWORD),
        ("ana", "short"),
        ("ana", "x" * 300),
        ("Not A Name!", PASSWORD),
    ],
    ids=["wrong password", "unknown name", "too short", "too long", "invalid name"],
)
async def test_every_wrong_login_gets_the_same_answer(
    settings: Settings, tmp_path: Path, name: str, password: str
) -> None:
    await add_user(settings, tmp_path)
    async with serve(settings, tmp_path) as client:
        answer = await login(client, name, password)
    assert answer.status_code == 401
    assert answer.json() == {
        "code": "wrong_credentials",
        "detail": "the name or the password is wrong",
    }
    assert "set-cookie" not in answer.headers


@pytest.mark.parametrize(
    "body", [b"", b"not json", b'{"name": "ana"}', b'{"name": "", "password": "x"}', b"[]"]
)
async def test_a_malformed_login_is_refused(
    settings: Settings, tmp_path: Path, body: bytes
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await client.post(
            "/api/auth/login", content=body, headers={"Content-Type": "application/json"}
        )
    assert answer.status_code == 401
    assert answer.json()["code"] == "wrong_credentials"


async def test_repeated_failures_lock_the_name_until_the_window_passes(
    settings: Settings, tmp_path: Path
) -> None:
    await add_user(settings, tmp_path)
    now = [datetime(2026, 11, 26, 12, tzinfo=UTC)]
    service = AuthService(settings, tmp_path, clock=lambda: now[0])
    for _ in range(settings.auth.lockout.max_failures):
        with pytest.raises(AuthError) as wrong:
            await service.login("ana", "wrong password here")
        assert wrong.value.failure is AuthFailure.WRONG_CREDENTIALS
    # Locked: even the right password is refused, with how long to wait.
    with pytest.raises(AuthError) as locked:
        await service.login("ana", PASSWORD)
    assert locked.value.failure is AuthFailure.TOO_MANY_ATTEMPTS
    assert 0 < locked.value.retry_after_s <= settings.auth.lockout.window_s + 1
    # Another name is not locked by ana's failures.
    await add_user(settings, tmp_path, "luis")
    assert await service.login("luis", PASSWORD)
    now[0] += timedelta(seconds=settings.auth.lockout.window_s)
    assert await service.user_of(await service.login("ana", PASSWORD)) == "ana"


async def test_the_lockout_answers_429_with_retry_after(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        for _ in range(settings.auth.lockout.max_failures):
            await login(client, "ana", "wrong password here")
        answer = await login(client, "ana", "wrong password here")
    assert answer.status_code == 429
    assert answer.json()["code"] == "too_many_attempts"
    assert int(answer.headers["retry-after"]) > 0


async def test_a_session_ends_after_its_lifetime(settings: Settings, tmp_path: Path) -> None:
    await add_user(settings, tmp_path)
    now = [datetime(2026, 11, 26, 12, tzinfo=UTC)]
    service = AuthService(settings, tmp_path, clock=lambda: now[0])
    token = await service.login("ana", PASSWORD)
    now[0] += timedelta(days=settings.auth.cookie.lifetime_days) - timedelta(seconds=1)
    assert await service.user_of(token) == "ana"
    now[0] += timedelta(seconds=1)
    assert await service.user_of(token) is None
    assert await service.user_of("") is None


async def test_a_new_password_or_a_removal_ends_the_users_sessions(
    settings: Settings, tmp_path: Path
) -> None:
    await add_user(settings, tmp_path)
    service = AuthService(settings, tmp_path)
    first = await service.login("ana", PASSWORD)
    await service.set_password("ana", "another long password")
    assert await service.user_of(first) is None
    with pytest.raises(AuthError):
        await service.login("ana", PASSWORD)
    second = await service.login("ana", "another long password")
    await service.remove_user("ana")
    assert await service.user_of(second) is None
    assert await service.users() == []


async def test_a_store_that_cannot_open_answers_503(settings: Settings, tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the folder should be")
    auth = settings.auth.model_copy(update={"database": blocked / "auth.sqlite"})
    broken = settings.model_copy(update={"auth": auth})
    async with serve(broken, tmp_path) as client:
        answer = await client.get("/api/map", headers={"Cookie": "subphora_session=x"})
        assert answer.status_code == 503
        assert answer.json()["code"] == "store_unavailable"
        refused = await login(client, "ana", PASSWORD)
        assert refused.status_code == 503


# ── Passwords and the store ──────────────────────────────────────────────────────────


def test_a_hash_carries_its_cost_and_salt(settings: Settings) -> None:
    auth: AuthSettings = settings.auth
    first, second = hash_password(PASSWORD, auth), hash_password(PASSWORD, auth)
    assert first != second
    assert first.startswith("scrypt$16$1$1$")
    assert verify_password(PASSWORD, first, auth)
    assert not verify_password("another password", first, auth)
    # A hash made at another cost still verifies after the settings change.
    assert verify_password(PASSWORD, first, cheap(fast_settings()).auth)


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "md5$abc",
        "scrypt$x$1$1$AA==$AA==",
        "scrypt$16$1$1$not base64!$AA==",
        "scrypt$1$1$1$AA==$AA==",
        "scrypt$16$1$1$AA==$",
    ],
)
def test_a_malformed_hash_never_verifies(settings: Settings, stored: str) -> None:
    assert not verify_password(PASSWORD, stored, settings.auth)


def test_the_store_keeps_only_a_digest_of_each_token(settings: Settings, tmp_path: Path) -> None:
    import asyncio
    import sqlite3

    asyncio.run(add_user(settings, tmp_path))
    token = asyncio.run(AuthService(settings, tmp_path).login("ana", PASSWORD))
    database = settings.auth.database_path(tmp_path)
    db = sqlite3.connect(database)
    try:
        rows = db.execute("SELECT token_sha256 FROM sessions").fetchall()
    finally:
        db.close()
    assert len(rows) == 1
    assert token not in rows[0][0]
    assert token.encode() not in database.read_bytes()


def test_an_existing_user_cannot_be_added_twice(settings: Settings, tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite", 1)
    now = datetime.now(UTC)
    store.add_user("ana", "h", now)
    with pytest.raises(AuthError) as twice:
        store.add_user("ana", "h", now)
    assert twice.value.failure is AuthFailure.USER_EXISTS
    for action in (lambda: store.set_password("nobody", "h"), lambda: store.remove_user("nobody")):
        with pytest.raises(AuthError) as unknown:
            action()
        assert unknown.value.failure is AuthFailure.UNKNOWN_USER


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"n": 1000}, "power of two"),
        ({"n": 1 << 20, "max_memory_mb": 16}, "max_memory_mb"),
    ],
)
def test_the_settings_refuse_an_impossible_cost(
    settings: Settings, update: dict[str, Any], message: str
) -> None:
    raw = settings.auth.password.scrypt.model_dump() | update
    with pytest.raises(ValidationError, match=message):
        type(settings.auth.password.scrypt).model_validate(raw)


def test_the_settings_refuse_a_maximum_below_the_minimum(settings: Settings) -> None:
    raw = settings.auth.password.model_dump() | {"min_length": 20, "max_length": 12}
    with pytest.raises(ValidationError, match="below min_length"):
        type(settings.auth.password).model_validate(raw)


def test_a_cookie_header_is_read_leniently() -> None:
    assert session_token("a=1; subphora_session=tok; b=2", "subphora_session") == "tok"
    assert session_token("", "subphora_session") == ""
    assert session_token("garbage", "subphora_session") == ""


# ── subphora users ───────────────────────────────────────────────────────────────────


@pytest.fixture
def cli_root(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(subphora.config, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    return tmp_path


def run(argv: list[str], monkeypatch: pytest.MonkeyPatch, stdin: str = "") -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return cli.main(argv)


def test_the_users_command_adds_lists_changes_and_removes(
    cli_root: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    assert run(["users", "list"], monkeypatch) == 0
    assert "no users yet" in capsys.readouterr().out
    assert run(["users", "add", "ana", "--password-stdin"], monkeypatch, PASSWORD + "\n") == 0
    assert run(["users", "list"], monkeypatch) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "ana"
    new = "a different long password\n"
    assert run(["users", "password", "ana", "--password-stdin"], monkeypatch, new) == 0
    assert "sign in again" in capsys.readouterr().out
    import asyncio

    service = AuthService(settings, cli_root)
    assert asyncio.run(service.login("ana", new.strip()))
    assert run(["users", "remove", "ana"], monkeypatch) == 0
    assert asyncio.run(service.users()) == []


@pytest.mark.parametrize(
    ("argv", "stdin", "message"),
    [
        (["users", "add", "Ana Pérez", "--password-stdin"], PASSWORD, "lower-case"),
        (["users", "add", "ana", "--password-stdin"], "short", "characters"),
        (["users", "remove", "nobody"], "", "no such user"),
        (["users", "password", "nobody", "--password-stdin"], PASSWORD, "no such user"),
    ],
)
def test_the_users_command_explains_a_refusal(
    cli_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    argv: list[str],
    stdin: str,
    message: str,
) -> None:
    assert run(argv, monkeypatch, stdin) == cli.EXIT_FAILED_CHECK
    assert message in capsys.readouterr().out


def test_the_users_command_asks_the_password_twice(
    cli_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    answers = iter([PASSWORD, "something else entirely"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    assert cli.main(["users", "add", "ana"]) == cli.EXIT_USAGE
    assert "differ" in capsys.readouterr().out
    answers = iter([PASSWORD, PASSWORD])
    assert cli.main(["users", "add", "ana"]) == 0
    assert run(["users", "add", "ana", "--password-stdin"], monkeypatch, PASSWORD) == 1
    assert "exists already" in capsys.readouterr().out


async def test_the_test_client_helper_signs_in(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings, root=tmp_path, transport=httpx.MockTransport(_no_network))
    async with app.router.lifespan_context(app), signed_in(app, settings, tmp_path) as client:
        assert (await client.get("/api/auth/me")).json() == {"name": "tester"}
