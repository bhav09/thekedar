"""Unit tests for CloudWorkstationExecutor with injected RemoteExecutor."""

from __future__ import annotations

import pytest
from pathlib import Path
from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_shared.db import Workspace, init_db
from thekedar_shared.settings import Settings
from thekedar_execution.cloud import CloudWorkstationExecutor
from thekedar_execution.remote import InProcessFakeRemoteExecutor, set_global_executor, SyncResult


class MockWorkstationOps:
    def __init__(self) -> None:
        self.ensure_ready_calls = []

    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> object:
        self.ensure_ready_calls.append((tenant_id, config_id))
        return None

    async def sync_repo_and_test(self, tenant_id: str, run_id: str | None) -> object:
        return None


@pytest.mark.asyncio
async def test_cloud_workstation_executor_run(test_settings: Settings, tmp_path: Path) -> None:
    # Use a file-based SQLite database so connections share the same file
    db_file = tmp_path / "test.db"
    test_settings.database_url = f"sqlite:///{db_file}"
    test_settings.remote_executor = "fake"
    test_settings.demo_mode = True # keep in demo mode to allow mock adapter easily
    
    session_factory = init_db(test_settings.database_url)
    session = session_factory()
    ws = Workspace(
        tenant_id="tenant-123",
        name="test-ws",
        cloud_workstation_config_id="config-456",
    )
    session.add(ws)
    session.commit()
    session.close()

    fake_remote = InProcessFakeRemoteExecutor(test_settings)
    set_global_executor(fake_remote)

    ops = MockWorkstationOps()
    executor = CloudWorkstationExecutor(test_settings, ops)

    ctx = GlobalContext(
        snapshot_id="snapshot-1",
        tenant_id="tenant-123",
        repo="org/repo",
        sha="sha-1",
        branch="main",
    )
    plan = ExecutionPlan(
        summary="Test coding run",
        branch_name="feature-1",
        test_strategy="pytest",
    )

    # Execute run_coding
    res = await executor.run_coding(plan, ctx, "feature-1", "run-1")
    
    # Assert ensure_ready was called with correct config_id from DB lookup
    assert len(ops.ensure_ready_calls) == 1
    assert ops.ensure_ready_calls[0] == ("tenant-123", "config-456")

    # Clean up global mock
    set_global_executor(None)
