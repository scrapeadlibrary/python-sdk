"""Tests for the synchronous client."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from scrapeadlibrary import (
    Ad,
    AdDetail,
    AdsPage,
    Page,
    PageSummary,
    ScrapeAdLibrary,
    ScrapeAdLibraryError,
)

from .conftest import AD_DETAIL, CREDIT_HEADERS, PAGE, PAGE_SUMMARY, ad, ads_body


@pytest.fixture
def client(mock_api, api_key, base_url):
    c = ScrapeAdLibrary(api_key=api_key, base_url=base_url)
    yield c
    c.close()


class TestClientInit:
    def test_defaults(self, api_key):
        client = ScrapeAdLibrary(api_key=api_key)
        assert client.api_key == api_key
        assert client.base_url == "https://api.scrapeadlibrary.com"
        assert client.max_retries == 2
        assert client.credits_remaining is None
        client.close()

    def test_custom_base_url_strips_slash(self, api_key):
        client = ScrapeAdLibrary(api_key=api_key, base_url="https://custom.api.com/")
        assert client.base_url == "https://custom.api.com"
        client.close()

    def test_env_vars(self, monkeypatch):
        monkeypatch.setenv("SCRAPEADLIBRARY_API_KEY", "sal_from_env")
        monkeypatch.setenv("SCRAPEADLIBRARY_BASE_URL", "http://localhost:8000/")
        client = ScrapeAdLibrary()
        assert client.api_key == "sal_from_env"
        assert client.base_url == "http://localhost:8000"
        client.close()

    def test_argument_overrides_env(self, monkeypatch):
        monkeypatch.setenv("SCRAPEADLIBRARY_API_KEY", "sal_from_env")
        client = ScrapeAdLibrary(api_key="sal_arg")
        assert client.api_key == "sal_arg"
        client.close()

    def test_missing_key_raises(self):
        with pytest.raises(ScrapeAdLibraryError, match="SCRAPEADLIBRARY_API_KEY"):
            ScrapeAdLibrary()

    def test_context_manager(self, api_key):
        with ScrapeAdLibrary(api_key=api_key) as client:
            assert client.api_key == api_key

    def test_sends_auth_and_user_agent(self, client, mock_api, api_key):
        route = mock_api.get("/v1/pages/1").respond(200, json={"data": PAGE})
        client.pages.get("1")
        request = route.calls.last.request
        assert request.headers["X-API-Key"] == api_key
        assert request.headers["User-Agent"].startswith("ScrapeAdLibrary-Python/")


class TestAdsSearch:
    def test_search_returns_typed_page(self, client, mock_api):
        mock_api.get("/v1/ads/search", params={"q": "shoes"}).respond(
            200,
            json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_abc"),
            headers=CREDIT_HEADERS,
        )
        page = client.ads.search(q="shoes")
        assert isinstance(page, AdsPage)
        assert [a.id for a in page] == ["1", "2"]
        assert len(page) == 2
        assert page.total_estimate == 6780
        assert page.has_more is True
        assert page.next_cursor == "c_abc"
        assert page.credits_used == 1
        assert page.cached is False
        assert page.media_expires_at == "2026-11-25T18:00:00Z"
        assert page.credits_remaining == 99
        assert client.credits_remaining == 99
        assert client.credits_used == 1

    def test_search_serialises_all_params(self, client, mock_api):
        route = mock_api.get("/v1/ads/search").respond(200, json=ads_body([]))
        client.ads.search(
            q="running shoes",
            page_id="15087023444",
            country="IT",
            status="all",
            ad_type="political",
            media_type="video",
            platforms=["facebook", "instagram"],
            languages=["it", "en"],
            active_from=date(2026, 1, 1),
            active_to="2026-02-01",
            match="exact",
            sort="impressions",
            limit=50,
            cursor="c_x",
        )
        params = dict(route.calls.last.request.url.params)
        assert params == {
            "q": "running shoes",
            "page_id": "15087023444",
            "country": "IT",
            "status": "all",
            "ad_type": "political",
            "media_type": "video",
            "platforms": "facebook,instagram",
            "languages": "it,en",
            "active_from": "2026-01-01",
            "active_to": "2026-02-01",
            "match": "exact",
            "sort": "impressions",
            "limit": "50",
            "cursor": "c_x",
        }

    def test_search_omits_unset_params(self, client, mock_api):
        route = mock_api.get("/v1/ads/search").respond(200, json=ads_body([]))
        client.ads.search(q="x")
        assert dict(route.calls.last.request.url.params) == {"q": "x"}

    def test_platforms_as_csv_string(self, client, mock_api):
        route = mock_api.get("/v1/ads/search").respond(200, json=ads_body([]))
        client.ads.search(q="x", platforms="facebook,threads")
        assert route.calls.last.request.url.params["platforms"] == "facebook,threads"


class TestAdModel:
    def test_nested_fields_are_typed(self, client, mock_api):
        mock_api.get("/v1/ads/search").respond(200, json=ads_body([ad("1")]))
        item = client.ads.search(q="x").data[0]
        assert isinstance(item, Ad)
        assert item.page.name == "Perfect themes"
        assert item.page.like_count == 18520
        assert item.cta.text == "Install now"
        assert item.images[0].url == "https://scontent.example/i.jpg"
        assert item.images[0].expires_at == "2026-11-25T18:00:00Z"
        assert item.cards[0].image.url == "https://scontent.example/c1.jpg"
        assert item.cards[0].cta is None
        assert item.is_active is True
        assert item.variants_count == 3

    def test_unknown_fields_are_kept_in_raw(self, client, mock_api):
        mock_api.get("/v1/ads/search").respond(200, json=ads_body([ad("1")]))
        item = client.ads.search(q="x").data[0]
        assert item.raw["some_future_field"] == {"nested": True}
        assert item.to_dict()["id"] == "1"

    def test_missing_fields_default(self):
        item = Ad.from_dict({"id": "42"})
        assert item.id == "42"
        assert item.images == [] and item.page is None and item.political is None

    def test_political(self):
        item = Ad.from_dict(
            ad(political={"spend": {"lower": 1, "upper": 2, "currency": "EUR", "text": "€1"}})
        )
        assert item.political.spend.currency == "EUR"
        assert item.political.impressions is None


class TestAdsGet:
    def test_get(self, client, mock_api):
        mock_api.get("/v1/ads/1550534860016399").respond(
            200,
            json={
                "data": AD_DETAIL,
                "credits_used": 2,
                "cached": True,
                "media_expires_at": "2026-11-25T18:00:00Z",
            },
            headers={"X-Credits-Used": "2", "X-Credits-Remaining": "40"},
        )
        result = client.ads.get("1550534860016399")
        detail = result.data
        assert isinstance(detail, AdDetail)
        assert detail.id == "1550534860016399"
        assert detail.advertiser.name == "Nike"
        assert detail.advertiser.instagram.followers == 300000000
        assert detail.payers[0].beneficiary == "person:1a2b3c4d"
        assert detail.transparency.eu.reach == 65104
        assert detail.transparency.eu.locations[0].name == "Italy"
        assert detail.transparency.eu.breakdown[0].male == 31
        assert detail.transparency.uk is None
        assert detail.cards[0].title == "Card 1"
        assert detail.removed is False
        assert result.credits_used == 2
        assert result.cached is True
        assert result.credits_remaining == 40

    def test_get_with_country(self, client, mock_api):
        route = mock_api.get("/v1/ads/1", params={"country": "DE"}).respond(
            200, json={"data": {"id": "1"}, "credits_used": 2, "cached": False}
        )
        assert client.ads.get("1", country="DE").data.id == "1"
        assert route.called


class TestPages:
    def test_get(self, client, mock_api):
        mock_api.get("/v1/pages/15087023444").respond(
            200, json={"data": PAGE, "credits_used": 1, "cached": False}, headers=CREDIT_HEADERS
        )
        result = client.pages.get("15087023444")
        assert isinstance(result.data, Page)
        assert result.data.category == "Sportswear Store"
        assert result.data.active_ads_estimate == 14386
        assert result.credits_used == 1
        assert result.credits_remaining == 99

    def test_ads(self, client, mock_api):
        route = mock_api.get("/v1/pages/15087023444/ads").respond(
            200, json=ads_body([ad("1")], has_more=True, next_cursor="c_1")
        )
        page = client.pages.ads("15087023444", country="US", status="inactive", limit=10)
        assert page.next_cursor == "c_1"
        assert dict(route.calls.last.request.url.params) == {
            "country": "US",
            "status": "inactive",
            "limit": "10",
        }

    def test_search(self, client, mock_api):
        route = mock_api.get("/v1/pages/search").respond(
            200, json={"data": [PAGE_SUMMARY], "credits_used": 1, "cached": False}
        )
        result = client.pages.search("nike", country="IT", limit=5)
        assert isinstance(result.data[0], PageSummary)
        assert result.data[0].ads_in_results == 4
        assert result.credits_used == 1
        assert dict(route.calls.last.request.url.params) == {
            "q": "nike",
            "country": "IT",
            "limit": "5",
        }


class TestPagination:
    def test_search_all_follows_cursors(self, client, mock_api):
        route = mock_api.get("/v1/ads/search")
        route.side_effect = [
            httpx.Response(
                200, json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_1")
            ),
            httpx.Response(200, json=ads_body([ad("3")], has_more=True, next_cursor="c_2")),
            httpx.Response(200, json=ads_body([ad("4")], has_more=False)),
        ]
        ids = [a.id for a in client.ads.search_all(q="shoes", country="IT")]
        assert ids == ["1", "2", "3", "4"]
        cursors = [c.request.url.params.get("cursor") for c in route.calls]
        assert cursors == [None, "c_1", "c_2"]
        # other params identical on every page
        assert all(c.request.url.params["country"] == "IT" for c in route.calls)

    def test_search_all_max_items(self, client, mock_api):
        route = mock_api.get("/v1/ads/search")
        route.side_effect = [
            httpx.Response(
                200, json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_1")
            ),
            httpx.Response(
                200, json=ads_body([ad("3"), ad("4")], has_more=True, next_cursor="c_2")
            ),
        ]
        ids = [a.id for a in client.ads.search_all(q="shoes", max_items=3)]
        assert ids == ["1", "2", "3"]
        assert route.call_count == 2
        # page size capped once at max_items and kept constant
        assert {c.request.url.params["limit"] for c in route.calls} == {"3"}

    def test_search_all_stops_at_max_without_extra_request(self, client, mock_api):
        route = mock_api.get("/v1/ads/search").respond(
            200, json=ads_body([ad("1"), ad("2")], has_more=True, next_cursor="c_1")
        )
        assert len(list(client.ads.search_all(q="x", max_items=2))) == 2
        assert route.call_count == 1

    def test_search_all_stops_on_empty_page(self, client, mock_api):
        route = mock_api.get("/v1/ads/search").respond(
            200, json=ads_body([], has_more=True, next_cursor="c_1")
        )
        assert list(client.ads.search_all(q="x")) == []
        assert route.call_count == 1

    def test_pages_ads_all(self, client, mock_api):
        route = mock_api.get("/v1/pages/9/ads")
        route.side_effect = [
            httpx.Response(200, json=ads_body([ad("1")], has_more=True, next_cursor="c_1")),
            httpx.Response(200, json=ads_body([ad("2")])),
        ]
        assert [a.id for a in client.pages.ads_all("9", limit=1)] == ["1", "2"]
        assert route.calls[1].request.url.params["cursor"] == "c_1"


class TestHealth:
    def test_health_check(self, client, mock_api):
        mock_api.get("/health").respond(200, json={"status": "healthy"})
        assert client.health_check() == {"status": "healthy"}
