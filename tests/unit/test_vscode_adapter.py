"""Unit tests for VSCodeAdapter enqueue/polling and the task queue API."""

from __future__ import annotations

import json
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from thekedar_shared.settings import Settings
from thekedar_shared.db import Workspace, init_db, IdeTask
from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.vscode import VSCodeAdapter


@pytest.mark.asyncio
async def test_vscode_adapter_enqueue_and_timeout(session_factory, test_settings: Settings, tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    test_settings.vscode_task_mode = "extension"
    test_settings.vscode_task_timeout_s = 1  # fast timeout
    test_settings.database_url = f"sqlite:///{db_file}"

    session = session_factory()
    # Create the ide_tasks table structure
    from thekedar_shared.db import Base
    session.execute(__import__("sqlalchemy").text("SELECT 1"))

    plan = ExecutionPlan(
        id="plan-1",
        summary="Code update for VS Code",
        files_to_touch=["vscode.py"],
        test_strategy="pytest",
        branch_name="feature/vscode",
    )
    context = GlobalContext(
        snapshot_id="snap-1",
        tenant_id="default",
        repo="thekedar/thekedar",
        sha="some-sha",
        branch="main",
    )

    adapter = VSCodeAdapter(test_settings)
    
    # Run task - should time out quickly and return success=False
    res = await adapter.run_task(plan, context, "feature/vscode")
    assert not res.success
    assert "timed out" in res.summary.lower() or "timeout" in res.summary.lower()


@pytest.mark.asyncio
async def test_vscode_adapter_enqueue_and_completion(session_factory, test_settings: Settings, tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test2.db"
    test_settings.vscode_task_mode = "extension"
    test_settings.vscode_task_timeout_s = 10
    test_settings.database_url = f"sqlite:///{db_file}"

    session = session_factory()

    plan = ExecutionPlan(
        id="plan-123",
        summary="A nice feature",
        files_to_touch=["main.py"],
        test_strategy="pytest",
        branch_name="feature/nice",
    )
    context = GlobalContext(
        snapshot_id="snap-123",
        tenant_id="tenant-vscode",
        repo="thekedar/thekedar",
        sha="some-sha",
        branch="main",
    )

    adapter = VSCodeAdapter(test_settings)

    # Let's mock asyncio.sleep so we don't block during test
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    # We will simulate another process completing the task in the database after 1 poll
    mock_session = session_factory()
    mock_session_factory_call = MagicMock(return_value=mock_session)
    monkeypatch.setattr("thekedar_shared.db.init_db", lambda url: mock_session_factory_call)

    # Initially, select returns pending. Then on second call we simulate "completed"
    original_session_execute = mock_session.execute
    call_count = 0

    class MockResult:
        def first(self):
            return ("completed", '{"success": true, "summary": "completed task!", "files_changed": ["main.py"], "commits_ahead": 1}')

    def mock_execute(statement, *args, **kwargs):
        nonlocal call_count
        stmt_str = str(statement)
        if "SELECT status, result_json" in stmt_str:
            call_count += 1
            if call_count == 1:
                return MockResult()
        return original_session_execute(statement, *args, **kwargs)

    monkeypatch.setattr(mock_session, "execute", mock_execute)

    res = await adapter.run_task(plan, context, "feature/nice")
    assert res.success
    assert res.summary == "completed task!"
    assert res.files_changed == ["main.py"]
    assert res.commits_ahead == 1
