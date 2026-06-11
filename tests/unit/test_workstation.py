"""Workstation lifecycle and remote executor integration tests."""

from datetime import UTC, datetime, timedelta
import pytest

from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_shared.db import WorkstationHealth, Workspace
from thekedar_shared.settings import Settings
from thekedar_execution.remote import InProcessFakeRemoteExecutor, set_global_executor


@pytest.mark.asyncio
async def test_hibernate_idle(session_factory, test_settings: Settings) -> None:
    session = session_factory()
    session.add(
        WorkstationHealth(
            tenant_id="default",
            name="ws-1",
            state="active",
            last_activity_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    session.commit()
    session.close()

    manager = WorkstationManager(test_settings, session_factory)
    count = await manager.hibernate_idle()
    assert count == 1

    session = session_factory()
    ws = session.query(WorkstationHealth).filter_by(tenant_id="default").first()
    assert ws is not None
    assert ws.state == "sleeping"
    session.close()


@pytest.mark.asyncio
async def test_ensure_ready_remote_executor(session_factory, test_settings: Settings) -> None:
    test_settings.remote_executor = "fake"
    fake_remote = InProcessFakeRemoteExecutor(test_settings)
    set_global_executor(fake_remote)

    manager = WorkstationManager(test_settings, session_factory)
    
    # 1. Initial boot ensures remote endpoint and DB updates state/host
    ws_health = await manager.ensure_ready("tenant-xyz", "config-xyz")
    assert ws_health.state == "active"
    assert ws_health.host == "fake-host"
    assert ws_health.instance_id == "fake-instance"

    # Clean up global mock
    set_global_executor(None)


@pytest.mark.asyncio
async def test_sync_repo_and_test_remote_executor(session_factory, test_settings: Settings) -> None:
    test_settings.remote_executor = "fake"
    fake_remote = InProcessFakeRemoteExecutor(test_settings)
    fake_remote.scripted_test_status = "passed"
    fake_remote.scripted_test_output = "Pytest passed on remote VM"
    set_global_executor(fake_remote)

    # Seed Workspace DB
    session = session_factory()
    workspace = Workspace(
        tenant_id="tenant-abc",
        name="Workspace ABC",
        github_repos="[\"org/repo-abc\"]"
    )
    session.add(workspace)
    session.commit()
    session.close()

    manager = WorkstationManager(test_settings, session_factory)
    record = await manager.sync_repo_and_test("tenant-abc", "run-abc")

    assert record.status == "passed"
    assert "remote" in record.summary or "Fake" in record.summary

    set_global_executor(None)
