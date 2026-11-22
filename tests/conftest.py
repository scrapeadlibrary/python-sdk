"""Shared test fixtures and sample payloads (shapes from docs/api.md)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
import respx

BASE_URL = "https://api.scrapeadlibrary.com"
API_KEY = "sal_test_key_for_unit_tests"

AD: dict[str, Any] = {
    "id": "1550534860016399",
    "url": "https://www.facebook.com/ads/library/?id=1550534860016399",
    "page": {
        "id": "115939511520844",
        "name": "Perfect themes",
        "profile_picture_url": "https://cdn.example/p.jpg",
        "is_person": False,
        "categories": ["Topic"],
        "like_count": 18520,
    },
    "status": "active",
    "started_at": "2026-05-19T07:00:00Z",
    "ended_at": None,
    "platforms": ["facebook", "instagram"],
    "format": "carousel",
    "body": "Download our themes",
    "title": "Perfect themes",
    "caption": "play.google.com",
    "link_url": "https://play.google.com/store/apps/details?id=x",
    "link_description": None,
    "cta": {"text": "Install now", "type": "install_mobile_app"},
    "images": [
        {
            "type": "image",
            "url": "https://scontent.example/i.jpg",
            "preview_url": "https://scontent.example/i_s.jpg",
            "sd_url": None,
            "expires_at": "2026-11-25T18:00:00Z",
        }
    ],
    "videos": [],
    "cards": [
        {
            "title": "Card 1",
            "body": "Body 1",
            "caption": "example.com",
            "link_url": "https://example.com/1",
            "cta": None,
            "image": {"type": "image", "url": "https://scontent.example/c1.jpg"},
            "video": None,
        }
    ],
    "variants_count": 3,
    "collation_id": "999",
    "categories": ["unknown"],
    "countries": ["IT"],
    "political": None,
    "contains_ai_generated_media": False,
    "some_future_field": {"nested": True},
}

POLITICAL = {
    "spend": {"lower": 7000, "upper": 8000, "currency": "EUR", "text": "€7K - €8K"},
    "impressions": {"text": ">1M"},
    "reach": {"text": ">1M"},
    "disclaimer": "Paid for by Example Party",
}

PAGE: dict[str, Any] = {
    "id": "15087023444",
    "name": "Nike",
    "is_person": False,
    "category": "Sportswear Store",
    "like_count": 39000000,
    "instagram": {"username": "nike", "followers": 300000000, "verified": True},
    "verified": True,
    "profile_picture_url": "https://cdn.example/nike.jpg",
    "cover_photo_url": None,
    "about": "Just do it",
    "deleted": False,
    "active_ads_estimate": 14386,
    "url": "https://www.facebook.com/ads/library/?view_all_page_id=15087023444",
}

AD_DETAIL: dict[str, Any] = {
    **AD,
    "advertiser": PAGE,
    "payers": [{"payer": "Company Ltd", "beneficiary": "person:1a2b3c4d"}],
    "transparency": {
        "eu": {
            "reach": 65104,
            "gender": "all",
            "age_min": 21,
            "age_max": 65,
            "locations": [{"name": "Italy", "type": "country", "excluded": False}],
            "breakdown": [
                {"country": "IT", "age_range": "18-24", "male": 31, "female": 1, "unknown": 0}
            ],
        },
        "uk": None,
    },
    "about": "page about text",
    "removed": False,
}

PAGE_SUMMARY = {
    "id": "15087023444",
    "name": "Nike",
    "is_person": False,
    "profile_picture_url": None,
    "categories": ["Sportswear Store"],
    "like_count": 123,
    "ads_in_results": 4,
}


def ad(ad_id: str = AD["id"], **overrides: Any) -> dict[str, Any]:
    data = copy.deepcopy(AD)
    data["id"] = ad_id
    data.update(overrides)
    return data


def ads_body(
    ads: list[dict[str, Any]],
    *,
    has_more: bool = False,
    next_cursor: str | None = None,
    total_estimate: int = 6780,
) -> dict[str, Any]:
    return {
        "data": ads,
        "total_estimate": total_estimate,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "credits_used": -(-len(ads) // 10),
        "cached": False,
        "media_expires_at": "2026-11-25T18:00:00Z",
    }


CREDIT_HEADERS = {"X-Credits-Used": "1", "X-Credits-Remaining": "99"}


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def api_key() -> str:
    return API_KEY


@pytest.fixture
def mock_api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        yield mock


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """Retries happen instantly in tests."""
    monkeypatch.setattr("scrapeadlibrary._client.retry_delay", lambda *a, **k: 0)
    monkeypatch.setattr("scrapeadlibrary._async_client.retry_delay", lambda *a, **k: 0)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("SCRAPEADLIBRARY_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPEADLIBRARY_BASE_URL", raising=False)
