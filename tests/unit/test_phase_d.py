"""Tests for Phase B/D: Agent bounds, cost ceiling, prompt isolation, and IDE sanitization."""

from __future__ import annotations

import uuid
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from thekedar_context.schemas import ExecutionPlan, GlobalContext, ImpactReport
from thekedar_ide_adapters.cursor import CursorAdapter
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.prompt import sanitize_plan_field
from thekedar_shared.settings import Settings
from thekedar_shared.db import AgentRun, Workspace, CostRecord, init_db, WorkstationHealth
from thekedar_orchestrator.coder_pipeline import CoderPipeline
from thekedar_orchestrator.services import OrchestratorServices


@pytest.mark.asyncio
async def test_ide_adapter_sanitization(test_settings: Settings, monkeypatch) -> None:
    test_settings.local_repo_path = "/tmp/repo"
    test_settings.demo_mode = True

    adapter = CursorAdapter(test_settings)
    plan = ExecutionPlan(
        id="plan-1",
        summary="A malicious summary; rm -rf /",
        files_to_touch=["test.py; touch hacked"],
        test_strategy="pytest; echo hacked",
        branch_name="feature/malicious",
    )
    context = GlobalContext(
        snapshot_id="snap-1",
        tenant_id="default",
        repo="thekedar/thekedar",
        sha="some-sha",
        branch="main",
    )

    monkeypatch.setattr(adapter, "healthcheck", AsyncMock(return_value=True))
    monkeypatch.setattr("thekedar_ide_adapters.cursor.checkout_branch", MagicMock())

    captured_cmd = []
    async def mock_create_subprocess_exec(*args, **kwargs):
        captured_cmd.extend(args)
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"success", b"")
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_create_subprocess_exec)
    monkeypatch.setattr("thekedar_ide_adapters.cursor.command_available", lambda x: True)
    monkeypatch.setattr("thekedar_ide_adapters.cursor.repo_path", lambda s, **kwargs: Path("/tmp/repo"))
    monkeypatch.setattr("thekedar_ide_adapters.cursor.post_run_metrics", lambda *args, **kwargs: CodingResult(success=True, summary="success"))

    res = await adapter.run_task(plan, context, "feature/malicious")
    assert res.success

    assert sanitize_plan_field("test.py; touch hacked") == "'test.py; touch hacked'"


@pytest.mark.asyncio
async def test_max_coding_iterations_enforcement(session_factory, test_settings: Settings) -> None:
    test_settings.max_coding_iterations = 2
    test_settings.database_url = "sqlite:///:memory:"

    session = session_factory()
    workspace = Workspace(
        tenant_id="tenant-max-it",
        name="Workspace Max It",
        cloud_workstation_config_id="config-max-it"
    )
    session.add(workspace)
    session.commit()

    # Create coder pipeline & workstation ops mock
    ws_ops = AsyncMock()
    ws_ops.ensure_ready.return_value = None
    ws_ops.sync_repo_and_test.return_value = MagicMock(status="passed", summary="pass")

    services = OrchestratorServices(test_settings, session_factory)
    pipeline = CoderPipeline(test_settings, session_factory, services._github, ws_ops)

    # 1. State with iteration count = 2 (under max=2) -> allowed
    state = {
        "run_id": str(uuid.uuid4()),
        "tenant_id": "tenant-max-it",
        "repo": "r",
        "global_context": GlobalContext(snapshot_id="s", tenant_id="tenant-max-it", repo="r", sha="abc", branch="main").model_dump(),
        "execution_plan": ExecutionPlan(summary="Fix it", branch_name="fix", test_strategy="pytest").model_dump(),
        "coding_iterations": 1,
    }
    
    # Mock executor.run_coding to succeed
    mock_executor = AsyncMock()
    mock_executor.run_coding.return_value = MagicMock(success=True, summary="all-good", files_changed=[], tests_added=1, tests_updated=0, commits_ahead=1, error=None)
    services._coder._execution._cloud = mock_executor
    test_settings.environment = "staging"
    test_settings.gcp_project_id = "some-project"

    res_state = await pipeline._node_execute_coding(state, workspace)
    assert res_state["coding_iterations"] == 2
    assert res_state.get("status") != "failed"

    # 2. State with iteration count = 2 before entering (meaning it will become 3, exceeding max=2) -> aborted
    state["coding_iterations"] = 2
    res_state = await pipeline._node_execute_coding(state, workspace)
    assert res_state["status"] == "failed"
    assert "maximum coding iterations" in res_state["reply"]

    session.close()


@pytest.mark.asyncio
async def test_cost_ceiling_hook_abort(session_factory, test_settings: Settings, monkeypatch) -> None:
    test_settings.database_url = "sqlite:///:memory:"
    test_settings.llm_provider = "openai"
    test_settings.llm_primary = "openai"
    test_settings.environment = "staging"

    session = session_factory()
    # Monthly budget is 10.00 USD
    workspace = Workspace(
        tenant_id="tenant-budget",
        name="Workspace Budget",
        budget_monthly_usd=10.00
    )
    # Total cost of 12.50 USD is logged, exceeding 10.00 budget
    session.add(workspace)
    session.add(CostRecord(tenant_id="tenant-budget", category="llm", amount_usd=12.50, run_id="run-1"))
    session.commit()

    from thekedar_orchestrator.llm.router import LLMRouter
    router = LLMRouter(test_settings, None)

    # Mock call_provider to return a mocked response
    monkeypatch.setattr(router, "_call_provider", AsyncMock(return_value=MagicMock()))

    # A call to complete with session should abort due to exceeded budget
    with pytest.raises(ValueError, match="exceeded monthly budget"):
        await router.complete("Some prompt", session=session, tenant_id="tenant-budget", run_id="run-1")

    session.close()
