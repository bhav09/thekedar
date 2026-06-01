"""Outbox and idempotency tests."""

from __future__ import annotations

import pytest
from thekedar_orchestrator.outbox import enqueue_outbound
from thekedar_shared.db import OutboundNotification
from thekedar_shared.idempotency import IdempotencyStore
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings


@pytest.mark.asyncio
async def test_idempotency_claim_after_publish_pattern() -> None:
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = IdempotencyStore(redis)

    assert await store.is_claimed("key-1") is False
    assert await store.claim("key-1") is True
    assert await store.is_claimed("key-1") is True
    assert await store.claim("key-1") is False


def test_enqueue_outbound(session_factory, test_settings: Settings) -> None:
    session = session_factory()
    msg = MessageEvent(
        channel=Channel.SLACK,
        message_id="m1",
        thread_id="C1",
        user_id="U1",
        tenant_id="default",
        text="hello",
        idempotency_key="k-out",
    )
    row_id = enqueue_outbound(session, test_settings, msg, "reply text", run_id="run-1")
    session.commit()
    row = session.get(OutboundNotification, row_id)
    assert row is not None
    assert row.status == "pending"
    import json
    body = json.loads(row.body)
    assert body["thread_ts"] == "C1"
    session.close()


def test_plan_requires_files_in_strict_mode() -> None:
    from thekedar_context.schemas import GlobalContext, ImpactReport
    from thekedar_orchestrator.plan import PlanGenerator
    from thekedar_shared.exceptions import IntegrationError

    ctx = GlobalContext(
        snapshot_id="s",
        tenant_id="t",
        repo="org/r",
        sha="abc",
        branch="main",
    )
    impact = ImpactReport(request_summary="task", affected_modules=[], confidence="low")
    with pytest.raises(IntegrationError):
        PlanGenerator().generate("fix something", ctx, impact, require_files=True)
