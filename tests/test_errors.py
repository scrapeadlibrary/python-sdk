"""Tests for error mapping and retries."""

from __future__ import annotations

import httpx
import pytest

from scrapeadlibrary import (
    AdNotFoundError,
    APIConnectionError,
    AuthenticationError,
    CursorError,
    InsufficientCreditsError,
    InternalServerError,
    InvalidParameterError,
    NotFoundError,
    PageNotFoundError,
    RateLimitError,
    ScrapeAdLibrary,
    ScrapeAdLibraryError,
    UpstreamError,
)
from scrapeadlibrary._base import retry_delay

from .conftest import PAGE


@pytest.fixture
def client(mock_api, api_key, base_url):
    c = ScrapeAdLibrary(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    c.close()


def _error(status: int, code: str, message: str = "boom", **extra):
    return httpx.Response(status, json={"error": code, "message": message, **extra})


@pytest.mark.parametrize(
    ("status", "code", "exc_class"),
    [
        (400, "invalid_parameter", InvalidParameterError),
        (400, "cursor_mismatch", CursorError),
        (401, "missing_api_key", AuthenticationError),
        (401, "invalid_api_key", AuthenticationError),
        (402, "insufficient_credits", InsufficientCreditsError),
        (404, "ad_not_found", AdNotFoundError),
        (404, "page_not_found", PageNotFoundError),
        (410, "cursor_expired", CursorError),
        (429, "rate_limit_exceeded", RateLimitError),
        (429, "insufficient_credits_retry_later", RateLimitError),
        (502, "upstream_schema_changed", UpstreamError),
        (503, "upstream_unavailable", UpstreamError),
        (504, "upstream_timeout", UpstreamError),
        (500, "internal_server_error", InternalServerError),
    ],
)
def test_error_codes(client, mock_api, status, code, exc_class):
    mock_api.get("/v1/ads/search").mock(return_value=_error(status, code, "Something failed"))
    with pytest.raises(exc_class) as exc_info:
        client.ads.search(q="x")
    err = exc_info.value
    assert isinstance(err, ScrapeAdLibraryError)
    assert err.status_code == status
    assert err.code == code
    assert err.message == "Something failed"


def test_not_found_hierarchy(client, mock_api):
    mock_api.get("/v1/ads/1").mock(return_value=_error(404, "ad_not_found"))
    with pytest.raises(NotFoundError):
        client.ads.get("1")


def test_invalid_parameter_details(client, mock_api):
    mock_api.get("/v1/ads/search").mock(
        return_value=_error(400, "invalid_parameter", "bad country", details={"param": "country"})
    )
    with pytest.raises(InvalidParameterError) as exc_info:
        client.ads.search(q="x", country="XX")
    assert exc_info.value.param == "country"
    assert exc_info.value.details == {"param": "country"}


def test_rate_limit_retry_after(client, mock_api):
    mock_api.get("/v1/ads/search").mock(
        return_value=httpx.Response(
            429,
            json={"error": "rate_limit_exceeded", "message": "slow down"},
            headers={"Retry-After": "7"},
        )
    )
    with pytest.raises(RateLimitError) as exc_info:
        client.ads.search(q="x")
    assert exc_info.value.retry_after == 7.0


def test_rate_limit_retry_after_from_body(client, mock_api):
    mock_api.get("/v1/ads/search").mock(
        return_value=_error(429, "insufficient_credits_retry_later", "wait", retry_after=30)
    )
    with pytest.raises(RateLimitError) as exc_info:
        client.ads.search(q="x")
    assert exc_info.value.retry_after == 30.0


def test_unknown_code_falls_back_to_status(client, mock_api):
    mock_api.get("/v1/pages/1").mock(return_value=_error(404, "something_new"))
    with pytest.raises(NotFoundError):
        client.pages.get("1")


def test_fastapi_detail_wrapper(client, mock_api):
    mock_api.get("/v1/pages/1").mock(
        return_value=httpx.Response(
            401, json={"detail": {"error": "invalid_api_key", "message": "Invalid API key"}}
        )
    )
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.pages.get("1")


def test_non_json_error_body(client, mock_api):
    mock_api.get("/v1/pages/1").mock(return_value=httpx.Response(418, text="I'm a teapot"))
    with pytest.raises(ScrapeAdLibraryError) as exc_info:
        client.pages.get("1")
    assert type(exc_info.value) is ScrapeAdLibraryError
    assert exc_info.value.message == "I'm a teapot"
    assert exc_info.value.status_code == 418


class TestRetries:
    @pytest.fixture
    def retry_client(self, mock_api, api_key, base_url):
        c = ScrapeAdLibrary(api_key=api_key, base_url=base_url, max_retries=2)
        yield c
        c.close()

    @pytest.mark.parametrize("status", [429, 500, 503, 504])
    def test_retries_then_succeeds(self, retry_client, mock_api, status):
        route = mock_api.get("/v1/pages/1")
        route.side_effect = [
            _error(status, "x"),
            httpx.Response(200, json={"data": PAGE, "credits_used": 1, "cached": False}),
        ]
        assert retry_client.pages.get("1").data.name == "Nike"
        assert route.call_count == 2

    def test_gives_up_after_max_retries(self, retry_client, mock_api):
        route = mock_api.get("/v1/pages/1").mock(return_value=_error(503, "upstream_unavailable"))
        with pytest.raises(UpstreamError):
            retry_client.pages.get("1")
        assert route.call_count == 3

    @pytest.mark.parametrize(
        ("status", "code"),
        [
            (400, "invalid_parameter"),
            (402, "insufficient_credits"),
            (502, "upstream_schema_changed"),
        ],
    )
    def test_does_not_retry_permanent_errors(self, retry_client, mock_api, status, code):
        route = mock_api.get("/v1/pages/1").mock(return_value=_error(status, code))
        with pytest.raises(ScrapeAdLibraryError):
            retry_client.pages.get("1")
        assert route.call_count == 1

    def test_retries_network_errors(self, retry_client, mock_api):
        route = mock_api.get("/v1/pages/1")
        route.side_effect = [
            httpx.ConnectError("refused"),
            httpx.Response(200, json={"data": PAGE, "credits_used": 1, "cached": False}),
        ]
        assert retry_client.pages.get("1").data.id == PAGE["id"]

    def test_network_error_after_retries(self, retry_client, mock_api):
        mock_api.get("/v1/pages/1").mock(side_effect=httpx.ReadTimeout("timeout"))
        with pytest.raises(APIConnectionError):
            retry_client.pages.get("1")


class TestRetryDelay:
    def test_uses_retry_after_header(self):
        response = httpx.Response(429, headers={"Retry-After": "3"})
        assert retry_delay(0, response) == 3.0

    def test_caps_retry_after(self):
        response = httpx.Response(429, headers={"Retry-After": "3600"})
        assert retry_delay(0, response) == 60.0

    def test_exponential_backoff(self):
        assert 0.5 <= retry_delay(0) <= 0.75
        assert 2.0 <= retry_delay(2) <= 3.0
