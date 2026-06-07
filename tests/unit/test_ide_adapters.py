"""IDE adapter tests."""

from __future__ import annotations

import subprocess
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import select_adapter, CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_ide_adapters.cursor import CursorAdapter
from thekedar_ide_adapters.claude import ClaudeCodeAdapter
from thekedar_ide_adapters.antigravity import AntigravityAdapter
from thekedar_ide_adapters.vscode import VSCodeAdapter
from thekedar_ide_adapters.prompt import build_ide_prompt, post_run_metrics
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError


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
    assert result.tests_added == 1


def test_select_adapter_matrix(test_settings: Settings) -> None:
    test_settings.demo_mode = True
    test_settings.llm_provider = "openai"
    test_settings.ide_adapter = "mock"
    assert isinstance(select_adapter(test_settings), MockIDEAdapter)

    test_settings.ide_adapter = "cursor"
    assert isinstance(select_adapter(test_settings), CursorAdapter)

    test_settings.ide_adapter = "claude"
    assert isinstance(select_adapter(test_settings), ClaudeCodeAdapter)

    test_settings.ide_adapter = "antigravity"
    assert isinstance(select_adapter(test_settings), AntigravityAdapter)

    test_settings.ide_adapter = "vscode"
    assert isinstance(select_adapter(test_settings), VSCodeAdapter)


def test_select_adapter_staging_blocks_mock(test_settings: Settings) -> None:
    test_settings.environment = "staging"
    test_settings.demo_mode = False
    test_settings.ide_adapter = "mock"
    test_settings.llm_provider = "openai"

    with pytest.raises(ConfigurationError, match="not allowed in staging/prod"):
        select_adapter(test_settings)


@pytest.mark.asyncio
async def test_claude_antigravity_cwd(test_settings: Settings, monkeypatch) -> None:
    test_settings.environment = "local"
    test_settings.local_repo_path = "/fake/repo"
    
    adapter = ClaudeCodeAdapter(test_settings)
    monkeypatch.setattr(adapter, "healthcheck", AsyncMock(return_value=True))
    monkeypatch.setattr("thekedar_ide_adapters.claude.checkout_branch", MagicMock())
    monkeypatch.setattr("thekedar_ide_adapters.claude.repo_path", MagicMock(return_value=Path("/fake/repo")))

    captured_kwargs = {}
    async def mock_create_subprocess(*args, **kwargs):
        captured_kwargs.update(kwargs)
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"done", b"")
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_create_subprocess)
    monkeypatch.setattr("thekedar_ide_adapters.claude.post_run_metrics", MagicMock(return_value=CodingResult(success=True, summary="all-good")))

    ctx = GlobalContext(snapshot_id="s", tenant_id="t", repo="r", sha="abc", branch="main")
    plan = ExecutionPlan(summary="Fix it", branch_name="fix", test_strategy="pytest")
    await adapter.run_task(plan, ctx, "fix")

    assert captured_kwargs.get("cwd") == "/fake/repo"


def test_build_ide_prompt_has_tags(test_settings: Settings) -> None:
    ctx = GlobalContext(snapshot_id="s", tenant_id="t", repo="r", sha="abc", branch="main")
    plan = ExecutionPlan(summary="Fix it", branch_name="fix", test_strategy="pytest")
    prompt = build_ide_prompt(plan, ctx, "fix")
    assert "<ground_truth_context>" in prompt
    assert "</ground_truth_context>" in prompt


@pytest.mark.asyncio
async def test_vscode_adapter_enqueue_and_timeout(test_settings: Settings, session_factory) -> None:
    test_settings.database_url = "sqlite:///:memory:"
    test_settings.vscode_task_mode = "extension"
    test_settings.vscode_task_timeout_s = 2 # quick timeout for test

    # In Phase B, database might not have the table yet, so it won't successfully enqueue but will log and time out or fail.
    adapter = VSCodeAdapter(test_settings)
    ctx = GlobalContext(snapshot_id="s", tenant_id="t", repo="r", sha="abc", branch="main")
    plan = ExecutionPlan(summary="Fix it", branch_name="fix", test_strategy="pytest")

    res = await adapter.run_task(plan, ctx, "fix")
    # Should report fail-closed instead of fake success
    assert not res.success
