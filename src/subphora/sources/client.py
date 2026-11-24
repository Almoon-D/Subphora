# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The catalogue client: async HTTP that calls only catalogued hosts, politely.

- Every request, redirects included, goes to a host of the source catalogue or is refused
  (hard rule 4).
- A generic ``subphora/<version>`` User-Agent, no contact data.
- Per host: at most ``max_concurrent`` requests in flight and ``min_interval_s`` between
  request starts, the strictest of the services on that host.
- Transport errors (resets, timeouts) are retried; HTTP errors are returned as they are.
- Bodies are capped at ``max_response_bytes``: the client fetches samples, never bulk data.
"""

import asyncio
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import httpx

from subphora.config.sources import SourcesSettings

type Params = Mapping[str, str | list[str]]


class HostNotAllowedError(Exception):
    """A request to a host outside the source catalogue, or not over https (hard rule 4)."""

    def __init__(self, host: str, reason: str = "is not in the source catalogue") -> None:
        super().__init__(f"host {host!r} {reason}")
        self.host = host


class SourceError(Exception):
    """The service could not be reached or answered in a way the client refuses."""


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    url: str
    status_code: int
    headers: httpx.Headers
    content: bytes

    @property
    def content_type(self) -> str:
        return str(self.headers.get("content-type", ""))

    @property
    def text(self) -> str:
        return self.content.decode(_charset(self.content_type), errors="replace")


def _charset(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip('"')
    return "utf-8"


class _HostLimiter:
    """Concurrency and spacing of request starts for one host."""

    def __init__(self, max_concurrent: int, min_interval_s: float) -> None:
        self.slots = asyncio.Semaphore(max_concurrent)
        self._interval = min_interval_s
        self._lock = asyncio.Lock()
        self._last_start: float | None = None

    async def wait_turn(self) -> None:
        async with self._lock:
            if self._last_start is not None:
                delay = self._last_start + self._interval - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
            self._last_start = time.monotonic()


class CatalogueClient:
    """Use as ``async with CatalogueClient(settings.sources, version) as client``."""

    def __init__(
        self,
        sources: SourcesSettings,
        version: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # httpx logs every URL at INFO; a URL can carry a key (hard rule: no secrets in logs).
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self._settings = sources.client
        self._allowed = sources.allowed_hosts()
        self._limiters = _build_limiters(sources)
        timeout = httpx.Timeout(
            self._settings.read_timeout_s, connect=self._settings.connect_timeout_s
        )
        self._http = httpx.AsyncClient(
            headers={"User-Agent": self._settings.user_agent.format(version=version)},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            event_hooks={"request": [self._refuse_unknown_host]},
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    @property
    def user_agent(self) -> str:
        return self._http.headers["User-Agent"]

    async def _refuse_unknown_host(self, request: httpx.Request) -> None:
        # Runs before every hop, so a redirect to another host or to http is refused too.
        self.ensure_allowed(request.url)

    def ensure_allowed(self, url: httpx.URL) -> None:
        if url.host.lower() not in self._allowed:
            raise HostNotAllowedError(url.host)
        if url.scheme != "https":
            raise HostNotAllowedError(url.host, f"is catalogued for https only, not {url.scheme}")

    async def get(
        self,
        url: str,
        params: Params | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> FetchedResponse:
        """GET ``url``; raises HostNotAllowedError or SourceError."""
        parsed = httpx.URL(url)
        self.ensure_allowed(parsed)
        limiter = self._limiters[parsed.host.lower()]
        attempts = self._settings.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                async with limiter.slots:
                    await limiter.wait_turn()
                    return await self._fetch(url, params, headers)
            except httpx.TransportError as exc:
                if attempt == attempts:
                    raise SourceError(_describe(exc, attempts)) from exc
                await asyncio.sleep(self._settings.retry_backoff_s * attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    async def _fetch(
        self, url: str, params: Params | None, headers: Mapping[str, str] | None
    ) -> FetchedResponse:
        limit = self._settings.max_response_bytes
        # Merge, not replace: some base URLs carry a query of their own (?map=…).
        target = httpx.URL(url).copy_merge_params(params or {})
        request = self._http.build_request("GET", target, headers=headers)
        response = await self._http.send(request, stream=True)
        try:
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise SourceError(f"response larger than {limit} bytes")
        finally:
            await response.aclose()
        return FetchedResponse(
            url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            content=bytes(body),
        )


def _build_limiters(sources: SourcesSettings) -> dict[str, _HostLimiter]:
    strictest: dict[str, tuple[int, float]] = {}
    for service in sources.services:
        limits = service.politeness
        current = strictest.get(service.host)
        if current is None:
            strictest[service.host] = (limits.max_concurrent, limits.min_interval_s)
        else:
            strictest[service.host] = (
                min(current[0], limits.max_concurrent),
                max(current[1], limits.min_interval_s),
            )
    return {host: _HostLimiter(*limits) for host, limits in strictest.items()}


def _describe(exc: httpx.TransportError, attempts: int) -> str:
    tries = f"after {attempts} attempt{'s' if attempts > 1 else ''}"
    if isinstance(exc, httpx.ProxyError):
        return f"the network proxy refused the connection {tries} (network policy?)"
    if isinstance(exc, httpx.TimeoutException):
        return f"timed out {tries}"
    if isinstance(exc, httpx.ConnectError):
        return f"could not connect {tries}: {exc}"
    return f"{type(exc).__name__} {tries}: {exc}"
