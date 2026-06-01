"""Retry helpers built on tenacity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from thekedar_resilience.errors import ErrorClass, classify_error, retry_after_seconds

T = TypeVar("T")


def _is_retryable(exc: BaseException) -> bool:
    return classify_error(exc) in (ErrorClass.TRANSIENT, ErrorClass.RATE_LIMIT)


def with_retry(max_attempts: int = 3):
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )


class ResilientClient:
    """Wrap async callables with circuit breaker + retry."""

    def __init__(self, registry, provider: str, max_attempts: int = 3) -> None:
        self._registry = registry
        self._provider = provider
        self._max_attempts = max_attempts

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        await self._registry.check(self._provider)

        @with_retry(self._max_attempts)
        async def _inner() -> T:
            return await fn()

        try:
            result = await _inner()
            await self._registry.record_success(self._provider)
            return result
        except Exception as exc:
            if classify_error(exc) == ErrorClass.TRANSIENT:
                await self._registry.record_failure(self._provider)
            raise
