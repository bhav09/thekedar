"""Publish run resume events to the orchestrator worker."""

from __future__ import annotations

import json

import redis.asyncio as aioredis
from thekedar_shared.checkpoint import RunCheckpointStore
from thekedar_shared.settings import Settings


async def publish_run_resume(
    settings: Settings,
    *,
    run_id: str,
    approval_id: str,
    decision: str,
    user_message: str | None = None,
) -> None:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        store = RunCheckpointStore(client)
        await store.publish_resume(
            {
                "run_id": run_id,
                "approval_id": approval_id,
                "decision": decision,
                "user_message": user_message,
            }
        )
    finally:
        await client.aclose()


def publish_run_resume_sync(
    settings: Settings,
    *,
    run_id: str,
    approval_id: str,
    decision: str,
    user_message: str | None = None,
) -> None:
    import asyncio

    asyncio.run(
        publish_run_resume(
            settings,
            run_id=run_id,
            approval_id=approval_id,
            decision=decision,
            user_message=user_message,
        )
    )
