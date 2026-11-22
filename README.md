# ScrapeAdLibrary Python SDK

Official Python SDK for the [ScrapeAdLibrary](https://scrapeadlibrary.com) API: search the public Meta Ad Library
(Facebook, Instagram, Messenger, Audience Network, Threads), read full ad details with EU/UK
transparency data, and look up advertiser pages.

## Installation

```bash
pip install scrapeadlibrary
```

## Quick Start

```python
from scrapeadlibrary import ScrapeAdLibrary

client = ScrapeAdLibrary(api_key="sal_your_api_key")  # or set SCRAPEADLIBRARY_API_KEY

page = client.ads.search(q="running shoes", country="IT", limit=10)
print(page.total_estimate, "ads found")
for ad in page:
    print(ad.page.name, "|", ad.format, "|", ad.body)
    for image in ad.images:
        print("  ", image.url)  # signed CDN URL, valid until image.expires_at

print(client.credits_remaining)  # from the X-Credits-Remaining header
```

## Async Usage

```python
import asyncio

from scrapeadlibrary import AsyncScrapeAdLibrary


async def main():
    async with AsyncScrapeAdLibrary() as client:
        page = await client.ads.search(q="running shoes", country="US")
        async for ad in client.ads.search_all(q="running shoes", max_items=100):
            print(ad.id, ad.started_at)


asyncio.run(main())
```

## Configuration

| Argument | Env var | Default |
|---|---|---|
| `api_key` | `SCRAPEADLIBRARY_API_KEY` | required (keys start with `sal_`) |
| `base_url` | `SCRAPEADLIBRARY_BASE_URL` | `https://api.scrapeadlibrary.com` |
| `timeout` | | `30.0` seconds |
| `max_retries` | | `2` (on 429, 500, 503, 504 and network errors, honouring `Retry-After`) |

## API Reference

### Ads

```python
# Search (1 credit per 10 ads returned, rounded up; empty result = 0)
page = client.ads.search(
    q="running shoes",  # keyword, required unless page_id is given
    page_id=None,  # restrict to one advertiser
    country="IT",  # ISO-3166 alpha-2 or "ALL" (default)
    status="active",  # active (default) | inactive | all
    ad_type="all",  # all (default) | political
    media_type="video",  # all | image | video | meme | none
    platforms=["facebook", "instagram"],
    languages=["it"],
    active_from="2026-10-01",  # str or datetime.date
    active_to="2026-11-01",
    match="exact",  # any (default) | exact phrase
    sort="impressions",  # relevance (default) | impressions
    limit=30,  # 1-50
)
page.data, page.total_estimate, page.has_more, page.next_cursor
page.credits_used, page.cached, page.media_expires_at, page.credits_remaining

# Next page: same params + cursor
next_page = client.ads.search(q="running shoes", country="IT", cursor=page.next_cursor)

# Iterate over all results, following cursors
for ad in client.ads.search_all(q="running shoes", country="IT", max_items=200):
    ...

# Full detail of one ad (2 credits): advertiser, payers, EU (DSA) / UK transparency
detail = client.ads.get("1550534860016399", country="IT").data
print(detail.advertiser.name, detail.payers)
if detail.transparency and detail.transparency.eu:
    print("EU reach:", detail.transparency.eu.reach)
```

### Pages (advertisers)

```python
# Advertiser profile (1 credit)
nike = client.pages.get("15087023444").data
print(nike.name, nike.like_count, nike.active_ads_estimate)

# Ads of one advertiser (same filters as ads.search, without q)
page = client.pages.ads("15087023444", country="US", media_type="video")
for ad in client.pages.ads_all("15087023444", max_items=100):
    ...

# Advertisers that ran ads matching a keyword (1 credit per 10 results)
for adv in client.pages.search("sneakers", country="IT", limit=10):
    print(adv.id, adv.name, adv.ads_in_results)
```

### Models

Responses are typed dataclasses: `Ad`, `AdDetail`, `Media`, `Card`, `Page`, `PageSummary`,
`Transparency`, ... Parsing is tolerant: unknown fields never break the SDK and the original JSON is
always available as `model.raw` (or `model.to_dict()`).

Media URLs are signed CDN links that expire (`Media.expires_at`, `page.media_expires_at`, usually
after a few days): download what you need to keep.

## Error Handling

```python
from scrapeadlibrary import (
    ScrapeAdLibrary,
    AdNotFoundError,
    InsufficientCreditsError,
    RateLimitError,
    CursorError,
)

client = ScrapeAdLibrary()

try:
    ad = client.ads.get("123").data
except AdNotFoundError:
    print("No such ad")
except InsufficientCreditsError:
    print("Top up your credits")
except RateLimitError as e:
    print(f"Retry in {e.retry_after}s")
```

| Exception | HTTP | `error` codes |
|---|---|---|
| `ScrapeAdLibraryError` | any | base class (`.message`, `.status_code`, `.code`, `.details`) |
| `InvalidParameterError` | 400 | `invalid_parameter` (`.param`) |
| `CursorError` | 400 / 410 | `cursor_mismatch`, `cursor_expired` |
| `AuthenticationError` | 401 | `missing_api_key`, `invalid_api_key` |
| `InsufficientCreditsError` | 402 | `insufficient_credits` |
| `NotFoundError` → `AdNotFoundError`, `PageNotFoundError` | 404 | `ad_not_found`, `page_not_found` |
| `RateLimitError` | 429 | `rate_limit_exceeded`, `insufficient_credits_retry_later` (`.retry_after`) |
| `UpstreamError` | 502 / 503 / 504 | `upstream_schema_changed`, `upstream_unavailable`, `upstream_timeout` |
| `InternalServerError` | 500 | `internal_server_error` |
| `APIConnectionError` | — | network error or timeout after retries |

Failed requests cost 0 credits.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .

# Live check against the real API (spends a few credits)
SCRAPEADLIBRARY_API_KEY=sal_xxx .venv/bin/python examples_live.py
```

## License

MIT
