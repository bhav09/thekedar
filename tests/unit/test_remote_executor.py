"""Unit tests for RemoteExecutor abstraction and implementations."""

from __future__ import annotations

import pytest
from pathlib import Path
from thekedar_shared.settings import Settings
from thekedar_execution.remote import (
    select_remote_executor,
    LocalRemoteExecutor,
    InProcessFakeRemoteExecutor,
    GcpWorkstationRemoteExecutor,
    set_global_executor,
    CommandResult,
)


@pytest.mark.asyncio
async def test_select_remote_executor(test_settings: Settings) -> None:
    # 1. Default / local remote executor
    test_settings.remote_executor = "local"
    executor = select_remote_executor(test_settings)
    assert isinstance(executor, LocalRemoteExecutor)

    # 2. Fake remote executor
    test_settings.remote_executor = "fake"
    executor = select_remote_executor(test_settings)
    assert isinstance(executor, InProcessFakeRemoteExecutor)

    # 3. GCP workstation remote executor
    test_settings.remote_executor = "gcp"
    executor = select_remote_executor(test_settings)
    assert isinstance(executor, GcpWorkstationRemoteExecutor)


@pytest.mark.asyncio
async def test_fake_remote_executor(test_settings: Settings) -> None:
    executor = InProcessFakeRemoteExecutor(test_settings)
    endpoint = await executor.ensure_ready("tenant1", None)
    assert endpoint.host == "fake-host"
    assert endpoint.instance_id == "fake-instance"

    # Script custom results
    executor.scripted_cmd_results["ls -la"] = CommandResult(exit_code=0, stdout="custom output", stderr="")
    res = await executor.run_command("tenant1", ["ls", "-la"], "/cwd", 30)
    assert len(executor.commands_run) == 1
    assert res.exit_code == 0
    assert res.stdout == "custom output"


@pytest.mark.asyncio
async def test_local_remote_executor(test_settings: Settings, tmp_path: Path) -> None:
    test_settings.local_repo_path = str(tmp_path)
    executor = LocalRemoteExecutor(test_settings)

    endpoint = await executor.ensure_ready("tenant1", None)
    assert endpoint.host == "localhost"

    # Test run simple python command
    res = await executor.run_command("tenant1", ["python", "-c", "print('hello remote')"], str(tmp_path), 10)
    assert res.exit_code == 0
    assert "hello remote" in res.stdout

    # Test command timeout
    res = await executor.run_command("tenant1", ["python", "-c", "import time; time.sleep(10)"], str(tmp_path), 1)
    assert res.exit_code == -1
    assert "timed out" in res.stderr
