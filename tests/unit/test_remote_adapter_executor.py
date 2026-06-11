"""Unit tests for RemoteAdapterExecutor."""

from __future__ import annotations

import base64
import pytest
from pathlib import Path
from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_shared.settings import Settings
from thekedar_execution.remote import InProcessFakeRemoteExecutor, CommandResult
from thekedar_execution.remote_adapter_executor import RemoteAdapterExecutor


@pytest.mark.asyncio
async def test_remote_adapter_executor_run_claude(test_settings: Settings) -> None:
    test_settings.remote_executor = "fake"
    test_settings.ide_adapter = "claude"
    fake_remote = InProcessFakeRemoteExecutor(test_settings)

    # Mock command outputs
    fake_remote.scripted_cmd_results = {
        # git diff output
        "git diff --name-only origin/main...HEAD": CommandResult(
            exit_code=0, stdout="src/main.py\nsrc/utils.py\n", stderr=""
        ),
        # git rev-list output
        "git rev-list --count origin/main..feature-1": CommandResult(
            exit_code=0, stdout="2\n", stderr=""
        ),
    }

    executor = RemoteAdapterExecutor(test_settings, fake_remote)

    ctx = GlobalContext(
        snapshot_id="snapshot-1",
        tenant_id="tenant-123",
        repo="org/repo",
        sha="sha-1",
        branch="main",
    )
    plan = ExecutionPlan(
        summary="Test coding remotely",
        branch_name="feature-1",
        test_strategy="pytest",
    )

    res = await executor.run_coding(plan, ctx, "feature-1", "claude")

    assert res.success is True
    assert "Remote adapter claude completed on feature-1" in res.summary
    assert res.files_changed == ["src/main.py", "src/utils.py"]
    assert res.commits_ahead == 2

    # Verify write and execution commands were run remotely
    command_strings = [" ".join(cmd) for tenant, cmd in fake_remote.commands_run]

    # Verify writing prompt (uses base64 decode)
    assert any("base64 -d" in cmd for cmd in command_strings)
    # Verify executing claude
    assert any("claude -p" in cmd for cmd in command_strings)
    # Verify cleanup of prompt file
    assert any("rm -f .thekedar_prompt.txt" in cmd for cmd in command_strings)


@pytest.mark.asyncio
async def test_remote_adapter_executor_run_antigravity(test_settings: Settings) -> None:
    test_settings.remote_executor = "fake"
    test_settings.ide_adapter = "antigravity"
    fake_remote = InProcessFakeRemoteExecutor(test_settings)

    executor = RemoteAdapterExecutor(test_settings, fake_remote)

    ctx = GlobalContext(
        snapshot_id="snapshot-1",
        tenant_id="tenant-123",
        repo="org/repo",
        sha="sha-1",
        branch="main",
    )
    plan = ExecutionPlan(
        summary="Test coding remotely",
        branch_name="feature-1",
        test_strategy="pytest",
    )

    res = await executor.run_coding(plan, ctx, "feature-1", "antigravity")

    assert res.success is True
    assert "Remote adapter antigravity completed on feature-1" in res.summary

    command_strings = [" ".join(cmd) for tenant, cmd in fake_remote.commands_run]
    assert any("agy run --prompt" in cmd for cmd in command_strings)
