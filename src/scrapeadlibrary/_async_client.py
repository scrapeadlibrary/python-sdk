"""Asynchronous ScrapeAdLibrary client."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ._base import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    build_headers,
    parse_int_header,
    resolve_api_key,
    resolve_base_url,
    retry_delay,
    should_retry,
)
from .ads import AsyncAdsAPI
from .errors import APIConnectionError, raise_for_status
from .pages import AsyncPagesAPI


class AsyncScrapeAdLibrary:
    """
    Asynchronous client for the ScrapeAdLibrary API.

    Usage:
        async with AsyncScrapeAdLibrary(api_key="sal_xxx") as client:
            page = await client.ads.search(q="running shoes", country="IT")
            async for ad in client.ads.search_all(q="running shoes", max_items=100):
                print(ad.id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = resolve_api_key(api_key)
        self.base_url = resolve_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._headers = build_headers(self.api_key)
        self._last_response: httpx.Response | None = None

        self.ads = AsyncAdsAPI(self)
        self.pages = AsyncPagesAPI(self)

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``path`` and return the decoded JSON body."""
        return (await self._send(path, params)).json()

    async def _send(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET ``path`` with retries on rate limits, temporary failures and network errors."""
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                response = await self._http.get(url, params=params or None, headers=self._headers)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise APIConnectionError(f"Could not reach {self.base_url}: {exc}") from exc
                await asyncio.sleep(retry_delay(attempt))
                attempt += 1
                continue

            self._last_response = response
            if should_retry(response) and attempt < self.max_retries:
                await asyncio.sleep(retry_delay(attempt, response))
                attempt += 1
                continue

            raise_for_status(response)
            return response

    @property
    def credits_remaining(self) -> int | None:
        """Credits left after the last request (``X-Credits-Remaining`` header)."""
        return parse_int_header(self._last_response, "x-credits-remaining")

    @property
    def credits_used(self) -> int | None:
        """Credits charged by the last request (``X-Credits-Used`` header)."""
        return parse_int_header(self._last_response, "x-credits-used")

    async def health_check(self) -> dict[str, Any]:
        """Check API health status (no authentication, no credits)."""
        response = await self._http.get(f"{self.base_url}/health")
        raise_for_status(response)
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client (if the SDK created it)."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncScrapeAdLibrary:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
