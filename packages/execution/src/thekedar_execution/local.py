"""Local IDE executor — runs on developer machine."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import CodingResult, select_adapter
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class LocalIDEExecutor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _repo(self) -> Path | None:
        if self._settings.local_repo_path:
            return Path(self._settings.local_repo_path).resolve()
        return Path.cwd().resolve()

    async def run_coding(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str, run_id: str
    ) -> CodingResult:
        adapter = select_adapter(self._settings)
        if not await adapter.healthcheck():
            logger.warning("IDE adapter healthcheck failed — continuing with adapter anyway")
        return await adapter.run_task(plan, context, branch)

    async def run_tests(self, tenant_id: str, run_id: str | None) -> tuple[str, str]:
        repo = self._repo()
        if repo is None:
            return "failed", "No local repo path"

        if (repo / "pyproject.toml").is_file() or (repo / "pytest.ini").is_file():
            cmd = ["uv", "run", "pytest", "tests", "-q", "--tb=short"]
            if not _which("uv"):
                cmd = ["python", "-m", "pytest", "tests", "-q", "--tb=short"]
        elif (repo / "package.json").is_file():
            cmd = ["npm", "test"]
        else:
            return "passed", "No test runner detected — skipped"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(repo),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()[:2000]
        status = "passed" if proc.returncode == 0 else "failed"
        return status, output or status


def _which(name: str) -> bool:
    import shutil

    return shutil.which(name) is not None
