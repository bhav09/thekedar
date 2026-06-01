"""FastAPI dependencies for webhook ingress."""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Request
from thekedar_shared.bus import RedisMessageBus, create_message_bus
from thekedar_shared.idempotency import IdempotencyStore
from thekedar_shared.settings import get_settings


async def get_redis(request: Request) -> AsyncGenerator[aioredis.Redis, None]:
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    request.app.state.redis = client
    try:
        yield client
    finally:
        await client.aclose()


def get_idempotency(redis: aioredis.Redis) -> IdempotencyStore:
    return IdempotencyStore(redis)


def get_bus(redis: aioredis.Redis) -> RedisMessageBus:
    settings = get_settings()
    bus = create_message_bus(settings, redis)
    assert isinstance(bus, RedisMessageBus), "M2 local ingress expects Redis bus"
    return bus
