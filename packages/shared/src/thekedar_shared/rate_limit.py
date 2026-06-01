"""Redis-backed sliding-window rate limiter for webhooks."""

from __future__ import annotations

import time

import redis.asyncio as aioredis


class WebhookRateLimiter:
    def __init__(self, redis: aioredis.Redis, limit_rps: int) -> None:
        self._redis = redis
        self._limit = max(1, limit_rps)

    async def allow(self, key: str) -> bool:
        bucket = int(time.time())
        redis_key = f"thekedar:ratelimit:{key}:{bucket}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, 2)
        return int(count) <= self._limit
