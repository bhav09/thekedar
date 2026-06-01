"""Orchestrator worker CLI."""

import asyncio
import logging

import redis.asyncio as aioredis
from thekedar_shared.bus import RedisMessageBus, create_message_bus
from thekedar_shared.settings import get_settings

from thekedar_orchestrator.worker import OrchestratorWorker

logging.basicConfig(level=logging.INFO)


async def run_async() -> None:
    settings = get_settings()
    worker = OrchestratorWorker(settings)
    worker.seed_workstation_health()

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    bus = create_message_bus(settings, redis)
    if not isinstance(bus, RedisMessageBus):
        raise RuntimeError("Orchestrator local worker requires Redis bus")

    logging.info("Orchestrator worker started")
    while True:
        payload = await bus.consume_inbound(timeout=5)
        if payload is None:
            continue
        await worker.process_payload(payload)


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
