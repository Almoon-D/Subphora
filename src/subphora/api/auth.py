# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The login at the HTTP boundary (MASTER_PLAN §4.9).

``AuthGate`` stands in front of every route: a request without a live session gets 401
``unauthenticated``, except the login itself and the health check, which answer without
one. The session travels in a cookie that is HttpOnly (no script reads it), Secure (only
over HTTPS) and SameSite=Lax (another site's form cannot send it with a POST).

- ``POST /api/auth/login`` (name and password): the session cookie, or 401
  ``wrong_credentials``, or 429 ``too_many_attempts`` with ``Retry-After``.
- ``POST /api/auth/logout``: the session ends and the cookie is cleared.
- ``GET /api/auth/me``: who is signed in; the page asks it first.
- ``GET /api/health``: ``{"status": "ok"}``, for the deployment's health check.
"""

import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Receive, Scope, Send

from subphora.config import Settings
from subphora.domain.auth import AuthError, AuthFailure, Credentials, SignedIn
from subphora.services.auth import AuthService

_log = logging.getLogger(__name__)

LOGIN = "/api/auth/login"
HEALTH = "/api/health"
OPEN_PATHS = frozenset({LOGIN, HEALTH})

_STATUS = {
    AuthFailure.UNAUTHENTICATED: 401,
    AuthFailure.WRONG_CREDENTIALS: 401,
    AuthFailure.TOO_MANY_ATTEMPTS: 429,
    AuthFailure.STORE_UNAVAILABLE: 503,
}


def session_token(cookie_header: str, name: str) -> str:
    """The session's token in a ``Cookie`` header, or "" when there is none."""
    return cookie_parser(cookie_header).get(name, "")


def _failure(error: AuthError) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if error.retry_after_s:
        headers["Retry-After"] = str(error.retry_after_s)
    return JSONResponse(
        status_code=_STATUS.get(error.failure, 400),
        content={"code": error.failure.value, "detail": error.detail},
        headers=headers,
    )


class AuthGate:
    """Pure ASGI, so streamed request bodies (field media) pass through untouched."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._cookie = settings.auth.cookie.name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS:
            await self._app(scope, receive, send)
            return
        cookie = next(
            (value.decode("latin-1") for key, value in scope["headers"] if key == b"cookie"), ""
        )
        auth: AuthService = scope["app"].state.auth
        try:
            user = await auth.user_of(session_token(cookie, self._cookie))
        except AuthError as exc:
            _log.error("the users store failed: %s", exc.detail)
            await _failure(exc)(scope, receive, send)
            return
        if user is None:
            refusal = AuthError(AuthFailure.UNAUTHENTICATED, "sign in first")
            await _failure(refusal)(scope, receive, send)
            return
        scope.setdefault("state", {})["user"] = user
        await self._app(scope, receive, send)


def add_auth_routes(app: FastAPI, settings: Settings) -> None:
    cookie = settings.auth.cookie

    def service(request: Request) -> AuthService:
        auth: AuthService = request.app.state.auth
        return auth

    @app.get(HEALTH)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(LOGIN, response_model=None)
    async def login(request: Request) -> Response:
        try:
            credentials = Credentials.model_validate_json(await request.body())
        except ValidationError:
            return _failure(AuthError(AuthFailure.WRONG_CREDENTIALS, "a name and a password"))
        try:
            token = await service(request).login(credentials.name, credentials.password)
        except AuthError as exc:
            if exc.failure is AuthFailure.TOO_MANY_ATTEMPTS:
                _log.warning("a name was locked out after repeated failed logins")
            return _failure(exc)
        name = credentials.name.strip().lower()
        response = JSONResponse(
            SignedIn(name=name).model_dump(), headers={"Cache-Control": "no-store"}
        )
        response.set_cookie(
            cookie.name,
            token,
            max_age=cookie.lifetime_days * 86400,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.post("/api/auth/logout", status_code=204, response_class=Response)
    async def logout(request: Request) -> Response:
        token = session_token(request.headers.get("cookie", ""), cookie.name)
        await service(request).logout(token)
        response = Response(status_code=204)
        response.delete_cookie(cookie.name, path="/", secure=True, httponly=True, samesite="lax")
        return response

    @app.get("/api/auth/me")
    async def me(request: Request) -> SignedIn:
        return SignedIn(name=request.state.user)
