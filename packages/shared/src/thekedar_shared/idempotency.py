"""Redis-backed idempotency for webhook deduplication."""

from redis.asyncio import Redis


class IdempotencyStore:
    def __init__(
        self, redis: Redis, *, prefix: str = "thekedar:idem", ttl_seconds: int = 86400
    ) -> None:
        self._redis = redis
        self._prefix = prefix
        self._ttl = ttl_seconds

    def _key(self, idempotency_key: str) -> str:
        return f"{self._prefix}:{idempotency_key}"

    async def claim(self, idempotency_key: str) -> bool:
        """Return True if this is the first time seeing the key."""
        was_set = await self._redis.set(self._key(idempotency_key), "1", nx=True, ex=self._ttl)
        return bool(was_set)
