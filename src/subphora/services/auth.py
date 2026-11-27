# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The login's use cases (MASTER_PLAN §4.9): users added by a command, passwords hashed
with scrypt, sessions by a random token, and a lockout of a name after repeated failures.

A login answers the same for an unknown name, a wrong password and a password outside
the allowed lengths, and it spends the same hashing work on each, so the answer does not
tell which names exist. Hashing is CPU work and SQLite blocks, so both run in a worker
thread.
"""

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from subphora.config import Settings
from subphora.config.auth import AuthSettings, ScryptSettings
from subphora.domain.auth import USER_NAME_PATTERN, AuthError, AuthFailure
from subphora.store.auth import AuthStore

_SCHEME = "scrypt"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str, settings: AuthSettings) -> str:
    """``scrypt$n$r$p$salt$key``: the cost travels with the hash."""
    cost = settings.password.scrypt
    salt = secrets.token_bytes(settings.password.salt_bytes)
    key = _derive(password, salt, cost.n, cost.r, cost.p, settings.password.key_bytes, cost)
    return f"{_SCHEME}${cost.n}${cost.r}${cost.p}${_b64(salt)}${_b64(key)}"


def _derive(
    password: str, salt: bytes, n: int, r: int, p: int, length: int, cost: ScryptSettings
) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=max(cost.max_memory_mb, 128 * n * r // (1024 * 1024) + 1) * 1024 * 1024,
        dklen=length,
    )


def verify_password(password: str, stored: str, settings: AuthSettings) -> bool:
    """Whether ``password`` is the one hashed in ``stored``; a malformed hash never is."""
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != _SCHEME:
        return False
    try:
        n, r, p = (int(part) for part in parts[1:4])
        salt = base64.b64decode(parts[4], validate=True)
        key = base64.b64decode(parts[5], validate=True)
    except ValueError:
        return False
    if n < 2 or r < 1 or p < 1 or not key:
        return False
    candidate = _derive(password, salt, n, r, p, len(key), settings.password.scrypt)
    return hmac.compare_digest(candidate, key)


class AuthService:
    def __init__(
        self,
        settings: Settings,
        root: Path,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings.auth
        self._store = AuthStore(self._settings.database_path(root), self._settings.busy_timeout_s)
        self._clock = clock
        # Failed logins per name, newest last; only names that failed in the window.
        self._failures: dict[str, list[datetime]] = {}
        # Hashed once, for a name that does not exist, so its login costs the same.
        self._decoy: str | None = None

    # ── The commands (``subphora users …``) ───────────────────────────────────────────

    def check_name(self, name: str) -> str:
        if not re.fullmatch(USER_NAME_PATTERN, name):
            raise AuthError(
                AuthFailure.INVALID_NAME,
                "a name is 1 to 32 lower-case letters, digits, '.', '-' or '_', "
                "starting with a letter or digit",
            )
        return name

    def check_password(self, password: str) -> str:
        rules = self._settings.password
        if not rules.min_length <= len(password) <= rules.max_length:
            raise AuthError(
                AuthFailure.WEAK_PASSWORD,
                f"a password has {rules.min_length} to {rules.max_length} characters",
            )
        return password

    async def add_user(self, name: str, password: str) -> None:
        self.check_name(name)
        self.check_password(password)
        hashed = await asyncio.to_thread(hash_password, password, self._settings)
        await asyncio.to_thread(self._store.add_user, name, hashed, self._clock())

    async def set_password(self, name: str, password: str) -> None:
        self.check_name(name)
        self.check_password(password)
        hashed = await asyncio.to_thread(hash_password, password, self._settings)
        await asyncio.to_thread(self._store.set_password, name, hashed)

    async def remove_user(self, name: str) -> None:
        await asyncio.to_thread(self._store.remove_user, self.check_name(name))

    async def users(self) -> list[str]:
        return await asyncio.to_thread(self._store.users)

    # ── The login ────────────────────────────────────────────────────────────────────

    async def login(self, name: str, password: str) -> str:
        """A new session's token, or a refusal that never says which part was wrong."""
        key = name.strip().lower()
        now = self._clock()
        self._refuse_if_locked(key, now)
        if not await asyncio.to_thread(self._check, key, password):
            self._failures.setdefault(key, []).append(now)
            raise AuthError(AuthFailure.WRONG_CREDENTIALS, "the name or the password is wrong")
        self._failures.pop(key, None)
        token = secrets.token_urlsafe(32)
        expires = now + timedelta(days=self._settings.cookie.lifetime_days)
        await asyncio.to_thread(self._store.add_session, _token_digest(token), key, now, expires)
        return token

    async def user_of(self, token: str) -> str | None:
        """The user a session's token belongs to, while the session lasts."""
        if not token:
            return None
        return await asyncio.to_thread(
            self._store.session_user, _token_digest(token), self._clock()
        )

    async def logout(self, token: str) -> None:
        if token:
            await asyncio.to_thread(self._store.end_session, _token_digest(token))

    def _check(self, name: str, password: str) -> bool:
        """Whether the name exists and the password is its own, after the same hashing
        work whichever part is wrong."""
        known = re.fullmatch(USER_NAME_PATTERN, name) is not None
        stored = self._store.password_hash(name) if known else None
        rules = self._settings.password
        allowed = rules.min_length <= len(password) <= rules.max_length
        matches = verify_password(
            password if allowed else "", stored or self._decoy_hash(), self._settings
        )
        return stored is not None and allowed and matches

    def _decoy_hash(self) -> str:
        if self._decoy is None:
            self._decoy = hash_password(secrets.token_urlsafe(16), self._settings)
        return self._decoy

    def _refuse_if_locked(self, key: str, now: datetime) -> None:
        window = timedelta(seconds=self._settings.lockout.window_s)
        # Forget every failure older than the window, so the table never outgrows it.
        for name in list(self._failures):
            recent = [at for at in self._failures[name] if now - at < window]
            if recent:
                self._failures[name] = recent
            else:
                del self._failures[name]
        recent = self._failures.get(key, [])
        if len(recent) >= self._settings.lockout.max_failures:
            wait = window - (now - recent[0])
            raise AuthError(
                AuthFailure.TOO_MANY_ATTEMPTS,
                "too many failed logins for this name; try again later",
                retry_after_s=max(1, int(wait.total_seconds()) + 1),
            )
