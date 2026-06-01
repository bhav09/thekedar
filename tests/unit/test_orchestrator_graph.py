"""LangGraph orchestrator tests."""

import pytest
from thekedar_orchestrator.graph import build_graph
from thekedar_shared.schemas import Channel, MessageEvent


@pytest.mark.asyncio
async def test_graph_help_reply(orchestrator_services) -> None:
    graph = build_graph(orchestrator_services)
    result = await graph.ainvoke(
        {
            "message": {
                "channel": "slack",
                "message_id": "h1",
                "thread_id": "C1",
                "user_id": "U1",
                "tenant_id": "T001",
                "text": "hello",
                "mentioned_agents": [],
                "idempotency_key": "k1",
            }
        }
    )
    assert "Thekedar agents" in result["reply"]
    assert result["workflow"] == "help"


@pytest.mark.asyncio
async def test_graph_architect_jira(orchestrator_services, sample_slack_message) -> None:
    graph = build_graph(orchestrator_services)
    result = await graph.ainvoke(
        {"message": sample_slack_message.model_dump(mode="json"), "run_id": "run-1"}
    )
    assert result["workflow"] == "architect"
    assert "THE-" in result["reply"]


@pytest.mark.asyncio
async def test_graph_coder_creates_pr(orchestrator_services, sample_coder_message) -> None:
    graph = build_graph(orchestrator_services)
    result = await graph.ainvoke(
        {"message": sample_coder_message.model_dump(mode="json"), "run_id": "run-2"}
    )
    assert result["workflow"] == "coder"
    assert "PR ready" in result["reply"]
    assert result.get("issue_key") == "THE-42"


@pytest.mark.asyncio
async def test_graph_coder_merge_requires_approval(orchestrator_services) -> None:
    graph = build_graph(orchestrator_services)
    message = MessageEvent(
        channel=Channel.SLACK,
        message_id="m3",
        thread_id="C123",
        user_id="U123",
        tenant_id="T001",
        text="@Coder merge THE-42 deploy fix",
        mentioned_agents=["Coder"],
        idempotency_key="slack:m3",
    )
    result = await graph.ainvoke(
        {"message": message.model_dump(mode="json"), "run_id": "run-3"}
    )
    assert result["workflow"] == "coder"
    assert "Approval required" in result["reply"]
    assert result.get("status") == "awaiting_approval"
