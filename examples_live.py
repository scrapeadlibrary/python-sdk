#!/usr/bin/env python3
"""
Live check of every ScrapeAdLibrary endpoint through the SDK (not part of the unit tests).

Spends a few credits (about 10). Responses are saved as JSON in output/.

Usage:
    SCRAPEADLIBRARY_API_KEY=sal_xxx python examples_live.py [keyword]
    SCRAPEADLIBRARY_BASE_URL=http://localhost:8000 SCRAPEADLIBRARY_API_KEY=sal_xxx \
        python examples_live.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from scrapeadlibrary import ScrapeAdLibrary, ScrapeAdLibraryError

OUTPUT_DIR = Path(__file__).parent / "output"
KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "running shoes"


def save(name: str, data: Any) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))


def step(name: str, fn: Callable[[], Any]) -> Any:
    print(f"- {name} ... ", end="", flush=True)
    try:
        result = fn()
    except ScrapeAdLibraryError as e:
        print(f"FAILED ({type(e).__name__}, {e.status_code}, {e.code}): {e.message}")
        return None
    print("ok")
    return result


def main() -> int:
    client = ScrapeAdLibrary()
    print(f"Base URL: {client.base_url}\n")
    failures = 0

    print("-", "health:", client.health_check())

    page = step("ads.search", lambda: client.ads.search(q=KEYWORD, country="ALL", limit=10))
    if page is None:
        return 1
    save("ads_search", [a.raw for a in page.data])
    print(
        f"  {len(page.data)} ads, total_estimate={page.total_estimate}, has_more={page.has_more}, "
        f"credits_used={page.credits_used}, credits_remaining={page.credits_remaining}"
    )
    if not page.data:
        print("No ads found, stopping.")
        return 1
    first = page.data[0]

    if page.next_cursor:
        nxt = step(
            "ads.search (cursor)",
            lambda: client.ads.search(q=KEYWORD, country="ALL", limit=10, cursor=page.next_cursor),
        )
        failures += nxt is None

    ads = step(
        "ads.search_all (max 15)", lambda: list(client.ads.search_all(q=KEYWORD, max_items=15))
    )
    failures += ads is None

    detail = step("ads.get", lambda: client.ads.get(first.id))
    failures += detail is None
    if detail:
        save("ad_detail", detail.data.raw)
        print(f"  advertiser={detail.data.advertiser and detail.data.advertiser.name}")

    page_id = first.page.id if first.page else None
    if page_id:
        profile = step("pages.get", lambda: client.pages.get(page_id))
        failures += profile is None
        if profile:
            save("page", asdict(profile.data))
        page_ads = step("pages.ads", lambda: client.pages.ads(page_id, limit=10))
        failures += page_ads is None
        all_page_ads = step(
            "pages.ads_all (max 5)", lambda: list(client.pages.ads_all(page_id, max_items=5))
        )
        failures += all_page_ads is None

    advertisers = step("pages.search", lambda: client.pages.search(KEYWORD, limit=5))
    failures += advertisers is None
    if advertisers:
        save("pages_search", [p.raw for p in advertisers.data])

    print(f"\nCredits remaining: {client.credits_remaining}")
    print(f"{'All endpoints OK' if not failures else f'{failures} step(s) failed'}")
    client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
