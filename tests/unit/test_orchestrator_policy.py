"""Orchestrator MCP policy integration."""

import pytest
from thekedar_orchestrator.policy_gate import PolicyViolation, enforce_mcp_policy
from thekedar_shared.settings import Settings


def test_policy_allows_github_tools(tmp_path) -> None:
    registry = tmp_path / "mcp-servers.yaml"
    registry.write_text(
        """
servers:
  - name: github
    image: ghcr.io/github/github-mcp-server:v1.1.2
    allowed_tools: [create_branch, create_pull_request]
"""
    )
    settings = Settings(THEKEDAR_MCP_REGISTRY_PATH=str(registry), THEKEDAR_DEMO_MODE=True)
    enforce_mcp_policy(settings, "github", "create_branch", {"branch": "thekedar/THE-1-x"})


def test_policy_denies_unknown_server(tmp_path) -> None:
    registry = tmp_path / "mcp-servers.yaml"
    registry.write_text("servers:\n  - name: github\n    image: x\n")
    settings = Settings(THEKEDAR_MCP_REGISTRY_PATH=str(registry), THEKEDAR_DEMO_MODE=True)
    with pytest.raises(PolicyViolation):
        enforce_mcp_policy(settings, "unknown", "any_tool")


@pytest.mark.asyncio
async def test_publish_enforces_mcp_policy(tmp_path, session_factory) -> None:
    from thekedar_orchestrator.coder_pipeline import CoderPipeline
    from thekedar_shared.db import Workspace, AgentRun
    from thekedar_context.schemas import ExecutionPlan, CompletionReport
    import json
    import uuid

    registry = tmp_path / "mcp-servers.yaml"
    registry.write_text(
        """
servers:
  - name: github
    image: ghcr.io/github/github-mcp-server:v1.1.2
    allowed_tools: []  # Empty allowlist denies all!
"""
    )
    settings = Settings(
        THEKEDAR_MCP_REGISTRY_PATH=str(registry),
        THEKEDAR_DEMO_MODE=True,
        THEKEDAR_DATABASE_URL="sqlite:///:memory:",
    )

    from unittest.mock import MagicMock
    mock_github = MagicMock()
    mock_workstation = MagicMock()

    pipeline = CoderPipeline(settings, session_factory, mock_github, mock_workstation)

    state = {
        "run_id": str(uuid.uuid4()),
        "repo": "org/repo",
        "tenant_id": "T-test",
        "execution_plan": ExecutionPlan(
            summary="test plan",
            branch_name="thekedar/THE-1-x",
            files_to_touch=[],
            instructions="",
        ).model_dump(),
        "completion_report": CompletionReport(
            summary="done",
            commits_ahead=1,
            tests_passed=True,
            modules_changed=[],
        ).model_dump(),
        "message": {
            "channel": "slack",
            "message_id": "m1",
            "thread_id": "C1",
            "user_id": "U1",
            "tenant_id": "T-test",
            "text": "test",
            "idempotency_key": "k1",
        }
    }

    session = session_factory()
    workspace = Workspace(
        tenant_id="T-test",
        name="Test",
        github_org="org",
        github_repos=json.dumps(["repo"]),
    )
    session.add(workspace)
    session.add(
        AgentRun(
            id=state["run_id"],
            tenant_id="T-test",
            channel="slack",
            user_id="U1",
            workflow="coder",
            status="running",
        )
    )
    session.commit()

    result = await pipeline._node_publish(state, workspace)
    assert result["status"] == "failed"
    assert "Publish blocked by policy constraint" in result["reply"]

    run = session.get(AgentRun, state["run_id"])
    assert run.status == "failed"
    session.close()
