"""Synchronous ScrapeAdLibrary client."""

from __future__ import annotations

import time
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
from .ads import AdsAPI
from .errors import APIConnectionError, raise_for_status
from .pages import PagesAPI


class ScrapeAdLibrary:
    """
    Synchronous client for the ScrapeAdLibrary API.

    Usage:
        client = ScrapeAdLibrary(api_key="sal_xxx")   # or set SCRAPEADLIBRARY_API_KEY
        page = client.ads.search(q="running shoes", country="IT")
        for ad in page:
            print(ad.page.name, ad.body)

        # Or as a context manager
        with ScrapeAdLibrary() as client:
            ad = client.ads.get("1550534860016399").data
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ):
        self.api_key = resolve_api_key(api_key)
        self.base_url = resolve_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self._headers = build_headers(self.api_key)
        self._last_response: httpx.Response | None = None

        self.ads = AdsAPI(self)
        self.pages = PagesAPI(self)

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``path`` and return the decoded JSON body."""
        return (self._send(path, params)).json()

    def _send(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET ``path`` with retries on rate limits, temporary failures and network errors."""
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                response = self._http.get(url, params=params or None, headers=self._headers)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise APIConnectionError(f"Could not reach {self.base_url}: {exc}") from exc
                time.sleep(retry_delay(attempt))
                attempt += 1
                continue

            self._last_response = response
            if should_retry(response) and attempt < self.max_retries:
                time.sleep(retry_delay(attempt, response))
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

    def health_check(self) -> dict[str, Any]:
        """Check API health status (no authentication, no credits)."""
        response = self._http.get(f"{self.base_url}/health")
        raise_for_status(response)
        return response.json()

    def close(self) -> None:
        """Close the underlying HTTP client (if the SDK created it)."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> ScrapeAdLibrary:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
