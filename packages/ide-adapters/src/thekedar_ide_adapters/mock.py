"""Mock IDE adapter for demo mode and tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, commits_ahead, repo_path, run_git
from thekedar_ide_adapters import CodingResult
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError


class MockIDEAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def healthcheck(self) -> bool:
        return True

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        if self._settings.environment in ("staging", "prod") and not self._settings.demo_mode:
            raise ConfigurationError("MockIDEAdapter is not allowed in staging/prod environments")

        repo = repo_path(self._settings, tenant_id=context.tenant_id, repo=context.repo)
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

        # Always write a unique test file to simulate real test additions
        test_dir = repo / "tests"
        test_dir.mkdir(exist_ok=True)
        safe_branch_name = "".join(c if c.isalnum() else "_" for c in branch)
        stub = test_dir / f"test_thekedar_{safe_branch_name}.py"
        stub.write_text(
            'def test_thekedar_stub():\n    assert True\n',
            encoding="utf-8",
        )
        run_git(repo, "add", f"tests/test_thekedar_{safe_branch_name}.py")
        run_git(repo, "commit", "-m", "thekedar: add stub test")
        tests_added = 1

        ahead = commits_ahead(repo, branch)
        return CodingResult(
            success=True,
            summary=f"Mock coding completed on {branch}",
            files_changed=[str(marker.relative_to(repo)), f"tests/test_thekedar_{safe_branch_name}.py"],
            tests_added=tests_added,
            commits_ahead=ahead,
        )
