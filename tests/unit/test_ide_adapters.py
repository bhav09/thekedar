"""IDE adapter tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import select_adapter
from thekedar_ide_adapters.mock import MockIDEAdapter


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


@pytest.mark.asyncio
async def test_mock_adapter_commits(test_settings, temp_git_repo: Path) -> None:
    test_settings.local_repo_path = str(temp_git_repo)
    adapter = MockIDEAdapter(test_settings)
    assert await adapter.healthcheck()

    ctx = GlobalContext(
        snapshot_id="s",
        tenant_id="default",
        repo="org/r",
        sha="abc",
        branch="main",
    )
    plan = ExecutionPlan(
        summary="Add feature",
        branch_name="the-42-feature",
        test_strategy="pytest",
    )
    result = await adapter.run_task(plan, ctx, plan.branch_name)
    assert result.success
    assert result.commits_ahead >= 1


def test_select_mock_in_demo(test_settings) -> None:
    test_settings.demo_mode = True
    adapter = select_adapter(test_settings)
    assert isinstance(adapter, MockIDEAdapter)
