"""Provider circuit breaker registry with optional Redis sync."""

from __future__ import annotations

from redis.asyncio import Redis
from thekedar_shared.settings import Settings

from thekedar_resilience.circuit_breaker import CircuitBreaker


class ProviderHealthRegistry:
    PREFIX = "thekedar:circuit:"

    def __init__(self, settings: Settings, redis: Redis | None = None) -> None:
        self._settings = settings
        self._redis = redis
        self._breakers: dict[str, CircuitBreaker] = {}

    def breaker(self, provider: str) -> CircuitBreaker:
        if provider not in self._breakers:
            self._breakers[provider] = CircuitBreaker(
                name=provider,
                failure_threshold=self._settings.circuit_failure_threshold,
                open_seconds=float(self._settings.circuit_open_seconds),
            )
        return self._breakers[provider]

    async def check(self, provider: str) -> None:
        cb = self.breaker(provider)
        if self._redis:
            raw = await self._redis.get(f"{self.PREFIX}{provider}")
            if raw == "open":
                cb._opened_at = cb._opened_at or __import__("time").monotonic()
        cb.check()

    async def record_success(self, provider: str) -> None:
        self.breaker(provider).record_success()
        if self._redis:
            await self._redis.delete(f"{self.PREFIX}{provider}")

    async def record_failure(self, provider: str) -> None:
        cb = self.breaker(provider)
        cb.record_failure()
        if self._redis and cb.is_open:
            await self._redis.setex(f"{self.PREFIX}{provider}", int(cb.open_seconds), "open")

    def snapshot(self) -> dict[str, str]:
        return {name: "open" if cb.is_open else "closed" for name, cb in self._breakers.items()}
