"""Tests for the asynchronous client."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from scrapeadlibrary import AdNotFoundError, AsyncScrapeAdLibrary, RateLimitError

from .conftest import AD_DETAIL, CREDIT_HEADERS, PAGE, PAGE_SUMMARY, ad, ads_body


@pytest_asyncio.fixture
async def client(base_url, api_key):
    c = AsyncScrapeAdLibrary(api_key=api_key, base_url=base_url)
    yield c
    await c.close()


async def test_env_api_key(monkeypatch):
    monkeypatch.setenv("SCRAPEADLIBRARY_API_KEY", "sal_env")
    async with AsyncScrapeAdLibrary() as c:
        assert c.api_key == "sal_env"
        assert c.base_url == "https://api.scrapeadlibrary.com"


async def test_search(client, mock_api):
    route = mock_api.get("/v1/ads/search").respond(
        200, json=ads_body([ad("1")], has_more=True, next_cursor="c_1"), headers=CREDIT_HEADERS
    )
    page = await client.ads.search(q="shoes", platforms=["instagram"], limit=10)
    assert page.data[0].page.name == "Perfect themes"
    assert page.next_cursor == "c_1"
    assert page.credits_remaining == 99
    assert client.credits_remaining == 99
    assert dict(route.calls.last.request.url.params) == {
        "q": "shoes",
        "platforms": "instagram",
        "limit": "10",
    }


async def test_search_all(client, mock_api):
    route = mock_api.get("/v1/ads/search")
    route.side_effect = [
        httpx.Response(200, json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_1")),
        httpx.Response(200, json=ads_body([ad("3")])),
    ]
    ids = [a.id async for a in client.ads.search_all(q="shoes")]
    assert ids == ["1", "2", "3"]
    assert route.calls[1].request.url.params["cursor"] == "c_1"


async def test_search_all_max_items(client, mock_api):
    route = mock_api.get("/v1/ads/search")
    route.side_effect = [
        httpx.Response(200, json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_1")),
        httpx.Response(200, json=ads_body([ad("3"), ad("4")], has_more=True, next_cursor="c_2")),
    ]
    ids = [a.id async for a in client.ads.search_all(q="shoes", max_items=3)]
    assert ids == ["1", "2", "3"]
    assert route.call_count == 2


async def test_get(client, mock_api):
    mock_api.get("/v1/ads/1550534860016399").respond(
        200, json={"data": AD_DETAIL, "credits_used": 2, "cached": False}
    )
    result = await client.ads.get("1550534860016399")
    assert result.data.transparency.eu.age_min == 21
    assert result.credits_used == 2


async def test_get_not_found(client, mock_api):
    mock_api.get("/v1/ads/0").respond(
        404, json={"error": "ad_not_found", "message": "Ad not found"}
    )
    with pytest.raises(AdNotFoundError, match="Ad not found"):
        await client.ads.get("0")


async def test_pages_get(client, mock_api):
    mock_api.get("/v1/pages/15087023444").respond(
        200, json={"data": PAGE, "credits_used": 1, "cached": True}
    )
    result = await client.pages.get("15087023444")
    assert result.data.instagram.username == "nike"
    assert result.cached is True


async def test_pages_ads_and_ads_all(client, mock_api):
    route = mock_api.get("/v1/pages/9/ads")
    route.side_effect = [
        httpx.Response(200, json=ads_body([ad("1")], has_more=True, next_cursor="c_1")),
        httpx.Response(200, json=ads_body([ad("2")])),
        httpx.Response(200, json=ads_body([ad("3")])),
    ]
    ids = [a.id async for a in client.pages.ads_all("9", media_type="video")]
    assert ids == ["1", "2"]
    page = await client.pages.ads("9")
    assert page.data[0].id == "3"
    assert route.calls[0].request.url.params["media_type"] == "video"


async def test_pages_search(client, mock_api):
    mock_api.get("/v1/pages/search", params={"q": "nike"}).respond(
        200, json={"data": [PAGE_SUMMARY], "credits_used": 1, "cached": False}
    )
    result = await client.pages.search("nike")
    assert result.data[0].name == "Nike"


async def test_retry_then_rate_limit_error(mock_api, api_key, base_url):
    route = mock_api.get("/v1/pages/1").respond(
        429, json={"error": "rate_limit_exceeded", "message": "slow"}, headers={"Retry-After": "2"}
    )
    async with AsyncScrapeAdLibrary(api_key=api_key, base_url=base_url, max_retries=1) as c:
        with pytest.raises(RateLimitError) as exc_info:
            await c.pages.get("1")
    assert exc_info.value.retry_after == 2.0
    assert route.call_count == 2


async def test_health_check(client, mock_api):
    mock_api.get("/health").respond(200, json={"status": "healthy"})
    assert await client.health_check() == {"status": "healthy"}
