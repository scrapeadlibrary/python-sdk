"""Pages API: advertiser profiles, their ads, and advertiser search."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from ._base import build_ads_params, compact, parse_int_header
from .ads import (
    AdType,
    Day,
    Match,
    MediaType,
    Sort,
    Status,
    StrList,
    _ads_page,
    _first_limit,
    _iterate,
)
from .types import Ad, AdsPage, PageResponse, PageSearchResult

if TYPE_CHECKING:
    from ._async_client import AsyncScrapeAdLibrary
    from ._client import ScrapeAdLibrary


class PagesAPI:
    """Sync pages API (``client.pages``)."""

    def __init__(self, client: ScrapeAdLibrary):
        self._client = client

    def get(self, page_id: str) -> PageResponse:
        """Get an advertiser page profile. Costs 1 credit."""
        response = self._client._send(f"/v1/pages/{page_id}")
        return PageResponse.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )

    def ads(
        self,
        page_id: str,
        *,
        country: str | None = None,
        status: Status | None = None,
        ad_type: AdType | None = None,
        media_type: MediaType | None = None,
        platforms: StrList | None = None,
        languages: StrList | None = None,
        active_from: Day | None = None,
        active_to: Day | None = None,
        match: Match | None = None,
        sort: Sort | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AdsPage:
        """
        List the ads of one advertiser page. Same filters as ``ads.search`` (without ``q``).

        Costs 1 credit per 10 ads returned (an empty result costs 0).
        """
        params = build_ads_params(
            country=country, status=status, ad_type=ad_type, media_type=media_type,
            platforms=platforms, languages=languages, active_from=active_from,
            active_to=active_to, match=match, sort=sort, limit=limit, cursor=cursor,
        )  # fmt: skip
        return _ads_page(self._client._send(f"/v1/pages/{page_id}/ads", params))

    def ads_all(
        self, page_id: str, *, max_items: int | None = None, **filters: Any
    ) -> Iterator[Ad]:
        """Iterate over every ad of a page, following ``next_cursor``."""
        filters["limit"] = _first_limit(filters.get("limit"), max_items)
        yield from _iterate(lambda cursor: self.ads(page_id, cursor=cursor, **filters), max_items)

    def search(
        self, q: str, country: str | None = None, limit: int | None = None
    ) -> PageSearchResult:
        """
        Find advertisers that ran ads matching ``q`` (deduplicated by page).

        Costs 1 credit per 10 advertisers returned (an empty result costs 0).

        Args:
            q: Keyword.
            country: ISO-3166 alpha-2 or ``"ALL"`` (default).
            limit: 1-30 (default 10).
        """
        response = self._client._send(
            "/v1/pages/search", compact(q=q, country=country, limit=limit)
        )
        return PageSearchResult.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )


class AsyncPagesAPI:
    """Async pages API (``client.pages``)."""

    def __init__(self, client: AsyncScrapeAdLibrary):
        self._client = client

    async def get(self, page_id: str) -> PageResponse:
        """Get an advertiser page profile. Costs 1 credit."""
        response = await self._client._send(f"/v1/pages/{page_id}")
        return PageResponse.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )

    async def ads(
        self,
        page_id: str,
        *,
        country: str | None = None,
        status: Status | None = None,
        ad_type: AdType | None = None,
        media_type: MediaType | None = None,
        platforms: StrList | None = None,
        languages: StrList | None = None,
        active_from: Day | None = None,
        active_to: Day | None = None,
        match: Match | None = None,
        sort: Sort | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AdsPage:
        """List the ads of one advertiser page. See :meth:`PagesAPI.ads`."""
        params = build_ads_params(
            country=country, status=status, ad_type=ad_type, media_type=media_type,
            platforms=platforms, languages=languages, active_from=active_from,
            active_to=active_to, match=match, sort=sort, limit=limit, cursor=cursor,
        )  # fmt: skip
        return _ads_page(await self._client._send(f"/v1/pages/{page_id}/ads", params))

    async def ads_all(
        self, page_id: str, *, max_items: int | None = None, **filters: Any
    ) -> AsyncIterator[Ad]:
        """Iterate over every ad of a page, following ``next_cursor``."""
        filters["limit"] = _first_limit(filters.get("limit"), max_items)
        cursor: str | None = None
        count = 0
        while True:
            page = await self.ads(page_id, cursor=cursor, **filters)
            for ad in page.data:
                if max_items is not None and count >= max_items:
                    return
                yield ad
                count += 1
            if not page.has_more or not page.next_cursor or not page.data:
                return
            if max_items is not None and count >= max_items:
                return
            cursor = page.next_cursor

    async def search(
        self, q: str, country: str | None = None, limit: int | None = None
    ) -> PageSearchResult:
        """Find advertisers that ran ads matching ``q``. See :meth:`PagesAPI.search`."""
        response = await self._client._send(
            "/v1/pages/search", compact(q=q, country=country, limit=limit)
        )
        return PageSearchResult.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )
