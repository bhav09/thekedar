"""HTTP and network error classification."""

from __future__ import annotations

from enum import StrEnum

import httpx


class ErrorClass(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RATE_LIMIT = "rate_limit"


def classify_error(exc: BaseException) -> ErrorClass:
    if isinstance(exc, httpx.TimeoutException):
        return ErrorClass.TRANSIENT
    if isinstance(exc, httpx.ConnectError):
        return ErrorClass.TRANSIENT
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return ErrorClass.RATE_LIMIT
        if code in (408, 500, 502, 503, 504):
            return ErrorClass.TRANSIENT
        return ErrorClass.PERMANENT
    return ErrorClass.PERMANENT


def retry_after_seconds(exc: BaseException) -> float | None:
    if isinstance(exc, httpx.HTTPStatusError):
        raw = exc.response.headers.get("Retry-After")
        if raw and raw.isdigit():
            return float(raw)
    return None
