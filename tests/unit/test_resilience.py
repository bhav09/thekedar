"""Resilience package tests."""

from __future__ import annotations

import httpx
import pytest
from thekedar_resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from thekedar_resilience.errors import ErrorClass, classify_error
from thekedar_resilience.retry import with_retry


def test_classify_transient_503() -> None:
    response = httpx.Response(503, request=httpx.Request("GET", "https://example.com"))
    exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
    assert classify_error(exc) == ErrorClass.TRANSIENT


def test_classify_rate_limit() -> None:
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
    exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
    assert classify_error(exc) == ErrorClass.RATE_LIMIT


def test_classify_permanent_400() -> None:
    response = httpx.Response(400, request=httpx.Request("GET", "https://example.com"))
    exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
    assert classify_error(exc) == ErrorClass.PERMANENT


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3, open_seconds=60)
    for _ in range(3):
        cb.record_failure()
    with pytest.raises(CircuitOpenError):
        cb.check()


def test_circuit_recovers_after_open_seconds() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, open_seconds=0.01)
    cb.record_failure()
    import time

    time.sleep(0.02)
    cb.check()
    cb.record_success()
    assert not cb.is_open


@pytest.mark.asyncio
async def test_retry_succeeds_on_eventual_success() -> None:
    calls = {"n": 0}

    @with_retry(max_attempts=3)
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.TimeoutException("timeout")
        return "ok"

    assert await flaky() == "ok"
    assert calls["n"] == 2
