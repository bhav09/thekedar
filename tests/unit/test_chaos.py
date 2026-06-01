"""Chaos-style resilience simulations (local, no external deps)."""

from __future__ import annotations

import pytest
from thekedar_shared.checkpoint import RunCheckpointStore
from thekedar_shared.run_ledger import RunLedger


@pytest.mark.asyncio
async def test_checkpoint_rebuild_from_sql_after_redis_miss(session_factory) -> None:
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ledger = RunLedger(session_factory)
    step_id = ledger.begin_step("crash-run", "default", "assess_impact")
    ledger.complete_step(step_id, {"impact_report": {"confidence": "high"}, "paused": True})

    store = RunCheckpointStore(redis, session_factory=session_factory)
    loaded = await store.load("crash-run")
    assert loaded is not None
    assert loaded["impact_report"]["confidence"] == "high"


@pytest.mark.asyncio
async def test_redis_dlq_replay(session_factory) -> None:
    import fakeredis.aioredis

    from thekedar_shared.bus import RedisMessageBus
    from thekedar_shared.dlq import DlqStore

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bus = RedisMessageBus(redis)
    dlq = DlqStore(redis, session_factory)
    payload = {"message": {"text": "test"}, "correlation_id": "c1"}

    await bus.nack_to_dlq(payload, error="simulated crash")
    assert await dlq.depth() == 1

    published: list[dict] = []

    async def publish_fn(item: dict) -> None:
        published.append(item)

    count = await dlq.replay_all(publish_fn, max_messages=1)
    assert count == 1
    assert published[0]["correlation_id"] == "c1"
