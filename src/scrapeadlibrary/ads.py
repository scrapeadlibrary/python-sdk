"""Ads API: search the ad library and fetch ad details."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import date
from typing import TYPE_CHECKING, Any, Literal, Union

from ._base import build_ads_params, compact, parse_int_header
from .types import Ad, AdDetailResponse, AdsPage

if TYPE_CHECKING:
    from ._async_client import AsyncScrapeAdLibrary
    from ._client import ScrapeAdLibrary

Status = Literal["active", "inactive", "all"]
AdType = Literal["all", "political"]
MediaType = Literal["all", "image", "video", "meme", "none"]
Match = Literal["any", "exact"]
Sort = Literal["relevance", "impressions"]
StrList = Union[str, Iterable[str]]
Day = Union[str, date]


def _first_limit(limit: int | None, max_items: int | None) -> int | None:
    """Page size for ``*_all`` iterators.

    The size is fixed for the whole iteration (a cursor only works with identical params), so it
    is capped once at ``max_items`` to avoid paying for ads that would be discarded.
    """
    if max_items is None:
        return limit
    return min(limit or 50, max_items)


class AdsAPI:
    """Sync ads API (``client.ads``)."""

    def __init__(self, client: ScrapeAdLibrary):
        self._client = client

    def search(
        self,
        q: str | None = None,
        *,
        page_id: str | None = None,
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
        Search ads by keyword and/or advertiser page.

        Costs 1 credit per 10 ads returned (an empty result costs 0).

        Args:
            q: Keyword (1-100 chars). Required unless ``page_id`` is given.
            page_id: Restrict to one advertiser page.
            country: ISO-3166 alpha-2 code or ``"ALL"`` (default ``ALL``).
            status: ``active`` (default), ``inactive`` or ``all``.
            ad_type: ``all`` (default) or ``political`` (political & issue ads).
            media_type: ``all``, ``image``, ``video``, ``meme`` or ``none``.
            platforms: Any of ``facebook, instagram, messenger, audience_network, threads``.
            languages: ISO-639-1 codes.
            active_from: ``YYYY-MM-DD`` (or ``date``); ads running at some point in the window.
            active_to: ``YYYY-MM-DD`` (or ``date``).
            match: ``any`` (default) or ``exact`` (exact phrase).
            sort: ``relevance`` (default) or ``impressions``.
            limit: Page size, 1-50 (default 30).
            cursor: ``next_cursor`` of the previous page; other params must be identical.
        """
        params = build_ads_params(
            q=q, page_id=page_id, country=country, status=status, ad_type=ad_type,
            media_type=media_type, platforms=platforms, languages=languages,
            active_from=active_from, active_to=active_to, match=match, sort=sort,
            limit=limit, cursor=cursor,
        )  # fmt: skip
        return _ads_page(self._client._send("/v1/ads/search", params))

    def search_all(
        self,
        q: str | None = None,
        *,
        max_items: int | None = None,
        **filters: Any,
    ) -> Iterator[Ad]:
        """
        Iterate over every ad matching the search, following ``next_cursor``.

        Takes the same filters as :meth:`search` (except ``cursor``). Stops after ``max_items``
        ads when given. Each page is billed as in :meth:`search`.
        """
        filters["limit"] = _first_limit(filters.get("limit"), max_items)
        yield from _iterate(lambda cursor: self.search(q, cursor=cursor, **filters), max_items)

    def get(self, ad_id: str, country: str | None = None) -> AdDetailResponse:
        """
        Get the full detail of one ad: advertiser, payers, EU/UK transparency. Costs 2 credits.

        Args:
            ad_id: Ad Library ID.
            country: ISO-3166 alpha-2 or ``"ALL"`` (default) for transparency data.
        """
        response = self._client._send(f"/v1/ads/{ad_id}", compact(country=country))
        return AdDetailResponse.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )


class AsyncAdsAPI:
    """Async ads API (``client.ads``)."""

    def __init__(self, client: AsyncScrapeAdLibrary):
        self._client = client

    async def search(
        self,
        q: str | None = None,
        *,
        page_id: str | None = None,
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
        """Search ads by keyword and/or advertiser page. See :meth:`AdsAPI.search`."""
        params = build_ads_params(
            q=q, page_id=page_id, country=country, status=status, ad_type=ad_type,
            media_type=media_type, platforms=platforms, languages=languages,
            active_from=active_from, active_to=active_to, match=match, sort=sort,
            limit=limit, cursor=cursor,
        )  # fmt: skip
        return _ads_page(await self._client._send("/v1/ads/search", params))

    async def search_all(
        self,
        q: str | None = None,
        *,
        max_items: int | None = None,
        **filters: Any,
    ) -> AsyncIterator[Ad]:
        """Iterate over every ad matching the search, following ``next_cursor``."""
        filters["limit"] = _first_limit(filters.get("limit"), max_items)
        cursor: str | None = None
        count = 0
        while True:
            page = await self.search(q, cursor=cursor, **filters)
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

    async def get(self, ad_id: str, country: str | None = None) -> AdDetailResponse:
        """Get the full detail of one ad. Costs 2 credits. See :meth:`AdsAPI.get`."""
        response = await self._client._send(f"/v1/ads/{ad_id}", compact(country=country))
        return AdDetailResponse.from_response(
            response.json(), parse_int_header(response, "x-credits-remaining")
        )


def _ads_page(response: Any) -> AdsPage:
    return AdsPage.from_response(response.json(), parse_int_header(response, "x-credits-remaining"))


def _iterate(fetch: Any, max_items: int | None) -> Iterator[Ad]:
    """Follow cursors until the results end or ``max_items`` ads were yielded."""
    cursor: str | None = None
    count = 0
    while True:
        page: AdsPage = fetch(cursor)
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
