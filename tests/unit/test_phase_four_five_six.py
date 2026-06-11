"""Unit tests for Phase IV, V, and VI features."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from thekedar_orchestrator.llm.router import LLMRouter, LLMResponse
from thekedar_orchestrator.policy_gate import is_destructive_command, verify_db_sandbox
from thekedar_execution.worktree_manager import GitWorktreeManager, ConcurrencyLimitExceeded
from thekedar_shared.db import Base, CostRecord, PendingApproval
from thekedar_shared.settings import Settings


def test_is_destructive_command() -> None:
    assert is_destructive_command("rm -rf /") is True
    assert is_destructive_command("drop table users") is True
    assert is_destructive_command("truncate table logs") is True
    assert is_destructive_command("python main.py") is False


def test_verify_db_sandbox(test_settings: Settings) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Disabled sandbox should pass unconditionally
        test_settings.opt_in_db_sandbox = False
        success, msg = verify_db_sandbox(test_settings, tmpdir)
        assert success is True
        assert msg == "DB sandbox disabled"

        # 2. Enabled sandbox with a mock db schema should pass dry-run
        test_settings.opt_in_db_sandbox = True
        # Create a mock db.py to trigger detection
        p = Path(tmpdir) / "packages/shared/src/thekedar_shared/db.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("class Base: pass")
        
        success, msg = verify_db_sandbox(test_settings, tmpdir)
        assert success is True
        assert "passed" in msg


def test_git_worktree_manager_mocked() -> None:
    # Use a real temporary git repo to test GitWorktreeManager behavior
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "main_repo"
        p.mkdir()
        # Initialize bare-minimum git repository
        subprocess_run = lambda args: __import__("subprocess").run(args, cwd=p, capture_output=True, text=True)
        subprocess_run(["git", "init"])
        subprocess_run(["git", "config", "user.email", "test@thekedar.ai"])
        subprocess_run(["git", "config", "user.name", "Test User"])
        (p / "README.md").write_text("Hello")
        subprocess_run(["git", "add", "README.md"])
        subprocess_run(["git", "commit", "-m", "initial commit"])

        # Test GitWorktreeManager
        manager = GitWorktreeManager(p, max_concurrency=2)
        assert len(manager.active_worktrees()) >= 1 # has at least main worktree

        # Allocate worktree 1
        w1 = manager.allocate_worktree("run-1", "feat-1")
        assert w1.exists()
        assert "run-1" in w1.name

        # Allocate worktree 2
        w2 = manager.allocate_worktree("run-2", "feat-2")
        assert w2.exists()

        # Allocate worktree 3 -> exceeds concurrency cap of 2
        with pytest.raises(ConcurrencyLimitExceeded):
            manager.allocate_worktree("run-3", "feat-3")

        # Cleanup
        manager.prune_worktree("run-1")
        assert not w1.exists()
        manager.prune_worktree("run-2")
        assert not w2.exists()


@pytest.mark.asyncio
async def test_llm_router_per_run_budget(test_settings: Settings) -> None:
    # Setup standard SQLite memory session
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Configure per-run cost limits
    test_settings.max_cost_per_run_usd = 0.10
    test_settings.max_tokens_per_run = 1000
    test_settings.llm_provider = "openai"
    test_settings.environment = "testing"

    # Add 1 cost record under run_id "run-cost-test" (amount = 0.05)
    session.add(CostRecord(tenant_id="default", category="llm", amount_usd=0.05, run_id="run-cost-test"))
    session.commit()

    router = LLMRouter(test_settings)
    
    # 1. Under budget, should proceed
    with patch.object(router, "_call_provider", return_value=LLMResponse(provider="gemini", content="ok", tokens_estimated=500)), \
         patch.object(router, "_providers", return_value=["gemini"]):
        res = await router.complete("hello", session=session, tenant_id="default", run_id="run-cost-test")
        assert res is not None
        assert res.content == "ok"

    # Commit the newly added cost (amount = 0.05 + 0.05 = 0.10)
    session.commit()

    # 2. Exceeds budget -> should abort with ValueError
    with patch.object(router, "_call_provider", return_value=LLMResponse(provider="gemini", content="ok", tokens_estimated=500)), \
         patch.object(router, "_providers", return_value=["gemini"]):
        with pytest.raises(ValueError) as exc:
            await router.complete("hello", session=session, tenant_id="default", run_id="run-cost-test")
        assert "Per-run cost limit" in str(exc.value)

    # Clean up
    session.close()
