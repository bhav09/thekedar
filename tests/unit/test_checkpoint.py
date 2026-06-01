"""RunCheckpointStore tests."""

from __future__ import annotations

import pytest
from thekedar_shared.checkpoint import RunCheckpointStore


@pytest.fixture
async def fake_redis():
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url("redis://localhost:6379/15", decode_responses=True)
        await client.ping()
    except Exception:
        pytest.skip("Redis not available")
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.mark.asyncio
async def test_checkpoint_save_load_delete(fake_redis) -> None:
    store = RunCheckpointStore(fake_redis)
    await store.save("run-1", {"status": "awaiting_approval", "node": "await_impact"})
    loaded = await store.load("run-1")
    assert loaded is not None
    assert loaded["node"] == "await_impact"
    await store.delete("run-1")
    assert await store.load("run-1") is None


@pytest.mark.asyncio
async def test_resume_queue(fake_redis) -> None:
    store = RunCheckpointStore(fake_redis)
    await store.publish_resume({"run_id": "r1", "approval_id": "a1", "decision": "approved"})
    payload = await store.consume_resume(timeout=2)
    assert payload is not None
    assert payload["run_id"] == "r1"
