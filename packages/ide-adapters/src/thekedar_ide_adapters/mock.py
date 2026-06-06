"""Mock IDE adapter for demo mode and tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, commits_ahead, repo_path, run_git
from thekedar_ide_adapters import CodingResult
from thekedar_shared.settings import Settings


class MockIDEAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def healthcheck(self) -> bool:
        return True

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        repo = repo_path(self._settings)
        if repo is None:
            return CodingResult(
                success=False,
                summary="No repo path configured",
                error="THEKEDAR_LOCAL_REPO_PATH not set",
            )

        checkout_branch(repo, branch)
        marker = repo / ".thekedar_run_marker"
        marker.write_text(f"run:{plan.summary}\n", encoding="utf-8")
        run_git(repo, "add", str(marker.relative_to(repo)))
        run_git(repo, "commit", "-m", f"thekedar: {plan.summary[:72]}")

        tests_added = 0
        test_dir = repo / "tests"
        if test_dir.is_dir():
            tests_added = 0
        else:
            test_dir.mkdir(exist_ok=True)
            stub = test_dir / "test_thekedar_stub.py"
            stub.write_text(
                'def test_thekedar_stub():\n    assert True\n',
                encoding="utf-8",
            )
            run_git(repo, "add", "tests/test_thekedar_stub.py")
            run_git(repo, "commit", "-m", "thekedar: add stub test")
            tests_added = 1

        ahead = commits_ahead(repo, branch)
        return CodingResult(
            success=True,
            summary=f"Mock coding completed on {branch}",
            files_changed=[str(marker.relative_to(repo))],
            tests_added=tests_added,
            commits_ahead=ahead,
        )
