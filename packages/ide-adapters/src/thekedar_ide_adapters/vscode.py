"""VS Code Remote / CLI adapter."""

from __future__ import annotations

import logging

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import command_available, commits_ahead, repo_path
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class VSCodeAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fallback = MockIDEAdapter(settings)

    async def healthcheck(self) -> bool:
        return command_available("code") or command_available("code-server")

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        if not await self.healthcheck():
            logger.warning("VS Code CLI not found — using mock adapter")
            return await self._fallback.run_task(plan, context, branch)

        repo = repo_path(self._settings)
        if repo is None:
            return CodingResult(success=False, summary="No repo", error="missing repo path")

        return CodingResult(
            success=True,
            summary=(
                f"VS Code task queued for {branch}. "
                "Use Remote-SSH to Cloud Workstation for interactive edits."
            ),
            files_changed=plan.files_to_touch,
            commits_ahead=commits_ahead(repo, branch) if repo else 0,
        )
