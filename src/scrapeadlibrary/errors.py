"""Typed exceptions mapped from the API's ``error`` codes."""

from __future__ import annotations

from typing import Any

import httpx


class ScrapeAdLibraryError(Exception):
    """Base error for the ScrapeAdLibrary SDK."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, status_code={self.status_code!r}, "
            f"code={self.code!r})"
        )


class APIConnectionError(ScrapeAdLibraryError):
    """The API could not be reached (network error or timeout), after retries."""


class AuthenticationError(ScrapeAdLibraryError):
    """Missing or invalid API key (401 ``missing_api_key`` / ``invalid_api_key``)."""


class InsufficientCreditsError(ScrapeAdLibraryError):
    """No credits left (402 ``insufficient_credits``)."""


class InvalidParameterError(ScrapeAdLibraryError):
    """A query parameter is invalid (400 ``invalid_parameter``)."""

    @property
    def param(self) -> str | None:
        """Name of the offending parameter, when the API reports it."""
        value = self.details.get("param")
        return str(value) if value is not None else None


class CursorError(ScrapeAdLibraryError):
    """The pagination cursor cannot be used.

    ``code`` is ``cursor_mismatch`` (400: the other params differ from the first page) or
    ``cursor_expired`` (410: restart from the first page).
    """


class NotFoundError(ScrapeAdLibraryError):
    """The requested resource does not exist (404)."""


class AdNotFoundError(NotFoundError):
    """The ad does not exist (404 ``ad_not_found``)."""


class PageNotFoundError(NotFoundError):
    """The advertiser page does not exist (404 ``page_not_found``)."""


class RateLimitError(ScrapeAdLibraryError):
    """Too many requests (429 ``rate_limit_exceeded`` / ``insufficient_credits_retry_later``).

    ``retry_after`` is the number of seconds to wait (``Retry-After`` header or body field).
    """

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class UpstreamError(ScrapeAdLibraryError):
    """The ad data source failed (502 ``upstream_schema_changed``, 503 ``upstream_unavailable``,
    504 ``upstream_timeout``). Usually temporary."""


class InternalServerError(ScrapeAdLibraryError):
    """Unexpected server error (500)."""


def parse_retry_after(response: httpx.Response) -> float | None:
    """Seconds from the ``Retry-After`` header, if present and numeric."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _retry_after(response: httpx.Response, body_value: Any) -> float | None:
    header = parse_retry_after(response)
    if header is not None:
        return header
    try:
        return max(0.0, float(body_value)) if body_value is not None else None
    except (TypeError, ValueError):
        return None


_ERROR_MAP: dict[str, type[ScrapeAdLibraryError]] = {
    "invalid_parameter": InvalidParameterError,
    "cursor_mismatch": CursorError,
    "cursor_expired": CursorError,
    "missing_api_key": AuthenticationError,
    "invalid_api_key": AuthenticationError,
    "insufficient_credits": InsufficientCreditsError,
    "ad_not_found": AdNotFoundError,
    "page_not_found": PageNotFoundError,
    "rate_limit_exceeded": RateLimitError,
    "insufficient_credits_retry_later": RateLimitError,
    "upstream_schema_changed": UpstreamError,
    "upstream_unavailable": UpstreamError,
    "upstream_timeout": UpstreamError,
    "internal_server_error": InternalServerError,
}

_STATUS_MAP: dict[int, type[ScrapeAdLibraryError]] = {
    400: InvalidParameterError,
    401: AuthenticationError,
    402: InsufficientCreditsError,
    404: NotFoundError,
    410: CursorError,
    422: InvalidParameterError,
    429: RateLimitError,
    500: InternalServerError,
    502: UpstreamError,
    503: UpstreamError,
    504: UpstreamError,
}


def error_from_response(response: httpx.Response) -> ScrapeAdLibraryError:
    """Build the typed exception for a non-2xx response."""
    message = f"HTTP {response.status_code}"
    code: str | None = None
    details: dict[str, Any] | None = None
    body_retry_after: Any = None
    try:
        body = response.json()
        if isinstance(body, dict):
            # FastAPI may wrap the error body in {"detail": {...}}
            if isinstance(body.get("detail"), dict):
                body = body["detail"]
            code = body.get("error") if isinstance(body.get("error"), str) else None
            message = str(body.get("message") or message)
            if isinstance(body.get("details"), dict):
                details = body["details"]
            body_retry_after = body.get("retry_after", (details or {}).get("retry_after"))
    except Exception:
        message = response.text or message

    exc_class = _ERROR_MAP.get(code or "") or _STATUS_MAP.get(
        response.status_code, ScrapeAdLibraryError
    )
    if exc_class is RateLimitError:
        return RateLimitError(
            message,
            status_code=response.status_code,
            code=code,
            details=details,
            retry_after=_retry_after(response, body_retry_after),
        )
    return exc_class(message, status_code=response.status_code, code=code, details=details)


def raise_for_status(response: httpx.Response) -> None:
    """Raise a typed exception if the response is not a success."""
    if not response.is_success:
        raise error_from_response(response)
