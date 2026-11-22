"""Shared configuration and helpers for the sync and async clients."""

from __future__ import annotations

import os
import random
from collections.abc import Iterable
from datetime import date
from typing import Any

import httpx

from .errors import ScrapeAdLibraryError, parse_retry_after

__version__ = "0.1.0"

# Brand: every brand-dependent value lives here.
BRAND_NAME = "ScrapeAdLibrary"
DEFAULT_BASE_URL = "https://api.scrapeadlibrary.com"
API_KEY_ENV = "SCRAPEADLIBRARY_API_KEY"
BASE_URL_ENV = "SCRAPEADLIBRARY_BASE_URL"
API_KEY_PREFIX = "sal_"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
USER_AGENT = f"{BRAND_NAME}-Python/{__version__}"

# Retried statuses: rate limits and temporary upstream/server failures. A failed request costs
# 0 credits, so retrying a GET is always safe. 502 (upstream schema changed) is not retried:
# it will not fix itself within seconds.
RETRY_STATUSES = frozenset({429, 500, 503, 504})
MAX_RETRY_DELAY = 60.0


def resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get(API_KEY_ENV)
    if not key:
        raise ScrapeAdLibraryError(
            f"No API key provided. Pass api_key=... or set the {API_KEY_ENV} environment variable."
        )
    return key


def resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def build_headers(api_key: str) -> dict[str, str]:
    """Build default headers for API requests."""
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


def parse_int_header(response: httpx.Response | None, name: str) -> int | None:
    if response is None:
        return None
    value = response.headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    """Seconds to wait before retry number ``attempt`` (0-based)."""
    if response is not None:
        retry_after = parse_retry_after(response)
        if retry_after is not None:
            return min(retry_after, MAX_RETRY_DELAY)
    base = 0.5 * (2**attempt)
    return min(base + random.uniform(0, base / 2), MAX_RETRY_DELAY)


def should_retry(response: httpx.Response) -> bool:
    return response.status_code in RETRY_STATUSES


def _csv(value: str | Iterable[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    items = [v for v in value if v]
    return ",".join(items) if items else None


def _day(value: str | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()[:10]
    return value


def build_ads_params(
    *,
    q: str | None = None,
    page_id: str | None = None,
    country: str | None = None,
    status: str | None = None,
    ad_type: str | None = None,
    media_type: str | None = None,
    platforms: str | Iterable[str] | None = None,
    languages: str | Iterable[str] | None = None,
    active_from: str | date | None = None,
    active_to: str | date | None = None,
    match: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Query params for ``/v1/ads/search`` and ``/v1/pages/{id}/ads`` (None values dropped)."""
    params: dict[str, Any] = {
        "q": q,
        "page_id": page_id,
        "country": country,
        "status": status,
        "ad_type": ad_type,
        "media_type": media_type,
        "platforms": _csv(platforms),
        "languages": _csv(languages),
        "active_from": _day(active_from),
        "active_to": _day(active_to),
        "match": match,
        "sort": sort,
        "limit": limit,
        "cursor": cursor,
    }
    return {k: v for k, v in params.items() if v is not None}


def compact(**params: Any) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}
