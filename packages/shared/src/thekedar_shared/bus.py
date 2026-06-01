"""Message bus — Redis queue locally, Pub/Sub in GCP."""

from __future__ import annotations

import json
from typing import Protocol

from google.cloud import pubsub_v1
from redis.asyncio import Redis

from thekedar_shared.dlq import DLQ_KEY
from thekedar_shared.settings import Settings


class MessageBus(Protocol):
    async def publish_inbound(self, payload: dict) -> None: ...
    async def consume_inbound(self, timeout: int = 5) -> dict | None: ...
    async def nack_to_dlq(self, payload: dict, *, error: str = "") -> None: ...


class RedisMessageBus:
    QUEUE_KEY = "thekedar:queue:inbound"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish_inbound(self, payload: dict) -> None:
        await self._redis.lpush(self.QUEUE_KEY, json.dumps(payload))

    async def consume_inbound(self, timeout: int = 5) -> dict | None:
        result = await self._redis.brpop(self.QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return json.loads(raw)

    async def nack_to_dlq(self, payload: dict, *, error: str = "") -> None:
        envelope = {"payload": payload, "error": error}
        await self._redis.lpush(DLQ_KEY, json.dumps(envelope, default=str))

    async def dlq_depth(self) -> int:
        return int(await self._redis.llen(DLQ_KEY))


class PubSubMessageBus:
    def __init__(self, settings: Settings) -> None:
        if not settings.pubsub_project_id:
            raise ValueError("pubsub_project_id required")
        self._settings = settings
        self._publisher = pubsub_v1.PublisherClient()
        self._subscriber = pubsub_v1.SubscriberClient()
        self._topic_path = self._publisher.topic_path(
            settings.pubsub_project_id,
            settings.inbound_topic,
        )
        self._subscription_path = self._subscriber.subscription_path(
            settings.pubsub_project_id,
            settings.inbound_subscription,
        )
        self._pending_ack: str | None = None

    async def publish_inbound(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        future = self._publisher.publish(self._topic_path, data)
        future.result(timeout=10)

    async def consume_inbound(self, timeout: int = 5) -> dict | None:
        response = self._subscriber.pull(
            request={"subscription": self._subscription_path, "max_messages": 1},
            timeout=timeout,
        )
        if not response.received_messages:
            return None
        message = response.received_messages[0]
        self._pending_ack = message.ack_id
        return json.loads(message.message.data.decode("utf-8"))

    async def ack(self) -> None:
        if self._pending_ack:
            self._subscriber.acknowledge(
                request={"subscription": self._subscription_path, "ack_ids": [self._pending_ack]}
            )
            self._pending_ack = None

    async def nack_to_dlq(self, payload: dict, *, error: str = "") -> None:
        if self._pending_ack:
            self._subscriber.modify_ack_deadline(
                request={
                    "subscription": self._subscription_path,
                    "ack_ids": [self._pending_ack],
                    "ack_deadline_seconds": 0,
                }
            )
            self._pending_ack = None


def create_message_bus(settings: Settings, redis: Redis) -> RedisMessageBus | PubSubMessageBus:
    if settings.pubsub_project_id and settings.environment in ("staging", "prod"):
        return PubSubMessageBus(settings)
    return RedisMessageBus(redis)
