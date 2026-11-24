# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The catalogue client: allowed hosts only, generic User-Agent, limits, retries, caps."""

import asyncio
import time

import httpx
import pytest
import respx

from subphora.sources import CatalogueClient, HostNotAllowedError, SourceError
from tests.support import catalogue, service

URL = "https://wms.example.org/wms"


async def test_a_host_outside_the_catalogue_is_refused_before_any_request() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get("https://evil.example.com/x")
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            with pytest.raises(HostNotAllowedError, match=r"evil\.example\.com"):
                await client.get("https://evil.example.com/x")
        assert not route.called


async def test_a_redirect_to_another_host_is_refused() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).respond(302, headers={"Location": "https://evil.example.com/x"})
        evil = mock.get("https://evil.example.com/x")
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            with pytest.raises(HostNotAllowedError):
                await client.get(URL)
        assert not evil.called


async def test_plain_http_is_refused_even_on_a_catalogued_host() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).respond(302, headers={"Location": "http://wms.example.org/wms"})
        plain = mock.get("http://wms.example.org/wms")
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            with pytest.raises(HostNotAllowedError, match="https only"):
                await client.get("http://wms.example.org/wms")
            with pytest.raises(HostNotAllowedError, match="https only"):
                await client.get(URL)
        assert not plain.called


async def test_a_redirect_within_the_catalogue_is_followed() -> None:
    with respx.mock as mock:
        mock.get(URL).respond(301, headers={"Location": "https://wms.example.org/new"})
        mock.get("https://wms.example.org/new").respond(200, text="moved")
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            response = await client.get(URL)
    assert response.text == "moved"
    assert response.url == "https://wms.example.org/new"


async def test_requests_carry_the_generic_user_agent_and_merge_the_query() -> None:
    entry = service(base_url="https://wms.example.org/map?map=/a.map")
    with respx.mock as mock:
        route = mock.get("https://wms.example.org/map").respond(200, text="ok")
        async with CatalogueClient(catalogue(entry), "1.2.3") as client:
            assert client.user_agent == "subphora/1.2.3"
            await client.get(entry["base_url"], params={"SERVICE": "WMS", "s": ["a", "b"]})
    request = route.calls.last.request
    assert request.headers["User-Agent"] == "subphora/1.2.3"
    assert request.url.params.get_list("s") == ["a", "b"]
    assert request.url.params["map"] == "/a.map"


async def test_http_errors_are_returned_not_retried() -> None:
    with respx.mock as mock:
        route = mock.get(URL).respond(503, text="busy")
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            response = await client.get(URL)
    assert response.status_code == 503
    assert route.call_count == 1


async def test_a_reset_connection_is_retried() -> None:
    with respx.mock as mock:
        route = mock.get(URL)
        route.side_effect = [httpx.ReadError("reset by peer"), httpx.Response(200, text="ok")]
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            response = await client.get(URL)
    assert response.text == "ok"
    assert route.call_count == 2


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx.ConnectTimeout("slow"), "timed out after 2 attempts"),
        (httpx.ReadTimeout("slow"), "timed out"),
        (httpx.ConnectError("refused"), "could not connect after 2 attempts"),
        (httpx.ProxyError("403"), "network proxy refused"),
        (httpx.RemoteProtocolError("empty reply"), "RemoteProtocolError after 2 attempts"),
    ],
)
async def test_transport_failures_end_in_a_source_error(error: Exception, reason: str) -> None:
    with respx.mock as mock:
        route = mock.get(URL).mock(side_effect=error)
        async with CatalogueClient(catalogue(service()), "1.2.3") as client:
            with pytest.raises(SourceError, match=reason):
                await client.get(URL)
    assert route.call_count == 2


async def test_without_retries_one_attempt_is_made() -> None:
    with respx.mock as mock:
        route = mock.get(URL).mock(side_effect=httpx.ConnectError("refused"))
        async with CatalogueClient(catalogue(service(), retries=0), "1.2.3") as client:
            with pytest.raises(SourceError, match="after 1 attempt:"):
                await client.get(URL)
    assert route.call_count == 1


async def test_a_body_over_the_cap_is_refused() -> None:
    with respx.mock as mock:
        mock.get(URL).respond(200, content=b"x" * 2_000)
        async with CatalogueClient(catalogue(service(), max_response_bytes=1_000), "1") as client:
            with pytest.raises(SourceError, match="larger than 1000 bytes"):
                await client.get(URL)


async def test_requests_to_one_host_respect_the_minimum_interval() -> None:
    slow = service(politeness={"max_concurrent": 4, "min_interval_s": 0.05, "cache_lifetime_s": 0})
    with respx.mock as mock:
        mock.get(URL).respond(200, text="ok")
        async with CatalogueClient(catalogue(slow), "1") as client:
            start = time.monotonic()
            await asyncio.gather(*(client.get(URL) for _ in range(3)))
            elapsed = time.monotonic() - start
    assert elapsed >= 0.1


async def test_services_on_one_host_share_the_strictest_limits() -> None:
    lax = service(
        id="a", politeness={"max_concurrent": 5, "min_interval_s": 0.0, "cache_lifetime_s": 0}
    )
    strict = service(
        id="b",
        base_url="https://wms.example.org/other",
        politeness={"max_concurrent": 1, "min_interval_s": 0.0, "cache_lifetime_s": 0},
    )
    in_flight = 0
    peak = 0

    async def answer(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200)

    with respx.mock as mock:
        mock.get(URL).mock(side_effect=answer)
        async with CatalogueClient(catalogue(lax, strict), "1") as client:
            await asyncio.gather(*(client.get(URL) for _ in range(4)))
    assert peak == 1


def test_the_charset_of_the_content_type_decodes_the_text() -> None:
    from subphora.sources.client import FetchedResponse

    body = "Catastro: información".encode("iso-8859-1")
    headers = httpx.Headers({"content-type": 'text/xml; charset="iso-8859-1"'})
    assert FetchedResponse("u", 200, headers, body).text == "Catastro: información"
    assert FetchedResponse("u", 200, httpx.Headers(), b"plain").content_type == ""
