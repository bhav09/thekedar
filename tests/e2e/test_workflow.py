"""End-to-end workflow tests (local, no external APIs)."""

import pytest
from thekedar_orchestrator.graph import build_graph
from thekedar_shared.db import PendingApproval, TicketCodeLink
from thekedar_shared.schemas import Channel, MessageEvent


@pytest.mark.asyncio
async def test_e2e_architect_to_coder(orchestrator_services, session_factory) -> None:
    graph = build_graph(orchestrator_services)

    architect_msg = MessageEvent(
        channel=Channel.WHATSAPP,
        message_id="w1",
        thread_id="user1",
        user_id="user1",
        tenant_id="PN123",
        text="@Architect create issue: Auth hardening",
        mentioned_agents=["Architect"],
        idempotency_key="wa:w1",
    )
    arch = await graph.ainvoke(
        {"message": architect_msg.model_dump(mode="json"), "run_id": "e2e-1"}
    )
    assert arch["workflow"] == "architect"
    assert "THE-" in arch["reply"]

    coder_msg = MessageEvent(
        channel=Channel.WHATSAPP,
        message_id="w2",
        thread_id="user1",
        user_id="user1",
        tenant_id="PN123",
        text="@Coder implement THE-42 auth fix and merge",
        mentioned_agents=["Coder"],
        idempotency_key="wa:w2",
    )
    coder = await graph.ainvoke(
        {"message": coder_msg.model_dump(mode="json"), "run_id": "e2e-2"}
    )
    assert coder["workflow"] == "coder"
    assert coder.get("pr_url")

    session = session_factory()
    link = session.query(TicketCodeLink).filter_by(issue_key="THE-42").first()
    assert link is not None
    assert link.pr_url
    approval = session.query(PendingApproval).filter_by(status="pending").first()
    assert approval is not None
    session.close()
