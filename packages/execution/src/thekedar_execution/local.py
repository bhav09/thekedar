"""Local IDE executor — runs on developer machine."""

from __future__ import annotations

import logging
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
        from thekedar_execution.remote import LocalRemoteExecutor
        executor = LocalRemoteExecutor(self._settings)
        path = self._repo()
        if path is None:
            return "failed", "No local repo path"
        return await executor.run_tests(tenant_id, str(path))
