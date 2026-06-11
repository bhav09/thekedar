"""Orchestrator worker CLI."""

import asyncio
import logging
import sys

import redis.asyncio as aioredis
from thekedar_shared.bus import RedisMessageBus, create_message_bus
from thekedar_shared.checkpoint import RunCheckpointStore
from thekedar_shared.dlq import DlqStore
from thekedar_shared.observability import configure_observability
from thekedar_shared.settings import get_settings

from thekedar_orchestrator.health import run_health_server
from thekedar_orchestrator.outbox import deliver_pending
from thekedar_orchestrator.worker import OrchestratorWorker, run_hibernate_monitor

logging.basicConfig(level=logging.INFO)


async def run_worker_async() -> None:
    settings = get_settings()
    # Orchestrator worker calls validate_settings on startup
    from thekedar_shared.prod_validation import assert_production_settings
    assert_production_settings(settings)

    configure_observability(settings, "orchestrator-worker")
    worker = OrchestratorWorker(settings)
    worker.seed()

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    bus = create_message_bus(settings, redis)
    worker.bind_redis(redis)
    checkpoints = RunCheckpointStore(redis, session_factory=worker.session_factory)
    dlq = DlqStore(redis, worker.session_factory)

    health_task = asyncio.create_task(run_health_server(worker, settings))

    logging.info("Orchestrator worker started")
    try:
        while True:
            payload = None
            if isinstance(bus, RedisMessageBus):
                payload = await bus.consume_inbound(timeout=2)
            else:
                payload = await bus.consume_inbound(timeout=2)

            if payload is not None:
                try:
                    await worker.process_payload(payload)
                    if hasattr(bus, "ack"):
                        await bus.ack()
                except Exception as exc:
                    logging.exception("Worker failed processing message")
                    await bus.nack_to_dlq(payload, error=str(exc))
                continue

            resume_payload = await checkpoints.consume_resume(timeout=1)
            if resume_payload is not None:
                resume_payload["type"] = "resume"
                await worker.process_payload(resume_payload)
                continue

            if worker._registry:
                await deliver_pending(
                    worker.session_factory, settings, limit=5, registry=worker._registry
                )
            
            await worker.expire_stale_approvals()
    finally:
        health_task.cancel()


def run() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "hibernate":
        run_hibernate_monitor(get_settings())
        return
    asyncio.run(run_worker_async())


if __name__ == "__main__":
    run()
