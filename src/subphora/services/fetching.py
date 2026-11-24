# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Fetch from a catalogued service through the file cache, for every use case.

The cache key is the URL and its sorted parameters; the lifetime is the catalogue's. A
fetched answer is stored only when the caller says it is usable (``store``), so an error
page or an empty answer is asked again next time.
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from subphora.config.sources import Service
from subphora.domain.provenance import Provenance
from subphora.sources import CatalogueClient, SourceError, SourceTimeoutError
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now

# A successful HTTP answer; anything else from a service is an upstream failure.
_HTTP_OK = 200


class UpstreamFailure(Exception):
    """The service did not answer usably; ``timeout`` tells a slow one from a broken one."""

    def __init__(self, detail: str, *, timeout: bool = False) -> None:
        super().__init__(detail)
        self.detail = detail
        self.timeout = timeout


@dataclass(frozen=True, slots=True)
class Fetched:
    content: bytes
    provenance: Provenance
    cache_key: str
    from_cache: bool


class CachedFetcher:
    def __init__(self, client: CatalogueClient, cache: FileCache, clock: Clock = utc_now) -> None:
        self._client = client
        self._cache = cache
        self._clock = clock

    async def fetch(self, service: Service, url: str, params: Mapping[str, str]) -> Fetched:
        """The cached answer if fresh, else the service's; raises UpstreamFailure."""
        key = _request_key(url, params)
        lifetime = service.politeness.cache_lifetime_s
        hit = await asyncio.to_thread(self._cache.get, service.id, key, lifetime)
        if hit is not None:
            return Fetched(hit.content, provenance(service, hit.fetched_at), key, True)
        try:
            response = await self._client.get(url, params, max_bytes=service.max_response_bytes)
        except SourceTimeoutError as exc:
            raise UpstreamFailure(f"{service.publisher}: {exc}", timeout=True) from exc
        except SourceError as exc:
            raise UpstreamFailure(f"{service.publisher}: {exc}") from exc
        if response.status_code != _HTTP_OK:
            raise UpstreamFailure(f"{service.publisher}: HTTP {response.status_code}")
        return Fetched(response.content, provenance(service, self._clock()), key, False)

    async def store(self, service: Service, fetched: Fetched) -> None:
        """Cache an answer the caller found usable (a no-op for one read from the cache)."""
        if fetched.from_cache:
            return
        await asyncio.to_thread(
            self._cache.put,
            service.id,
            fetched.cache_key,
            fetched.content,
            fetched.provenance.retrieved_at,
            service.politeness.cache_lifetime_s,
        )

    async def recall(self, service: Service, key: str) -> Fetched | None:
        """Something derived from a service's answer and kept under ``key``, if fresh."""
        lifetime = service.politeness.cache_lifetime_s
        hit = await asyncio.to_thread(self._cache.get, service.id, key, lifetime)
        if hit is None:
            return None
        return Fetched(hit.content, provenance(service, hit.fetched_at), key, True)

    async def remember(
        self, service: Service, key: str, content: bytes, source: Provenance
    ) -> None:
        """Keep something derived from a service's answer, dated like that answer."""
        await asyncio.to_thread(
            self._cache.put,
            service.id,
            key,
            content,
            source.retrieved_at,
            service.politeness.cache_lifetime_s,
        )


def _request_key(url: str, params: Mapping[str, str]) -> str:
    return url + "?" + urlencode(sorted(params.items()))


def provenance(service: Service, retrieved_at: datetime) -> Provenance:
    return Provenance(
        service_id=service.id,
        publisher=service.publisher,
        attribution=service.attribution,
        retrieved_at=retrieved_at,
    )
