"""Cursor CLI adapter."""

from __future__ import annotations

import asyncio
import logging

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, command_available, commits_ahead, repo_path
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class CursorAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fallback = MockIDEAdapter(settings)

    async def healthcheck(self) -> bool:
        return command_available("cursor") or command_available("cursor-agent")

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        repo = repo_path(self._settings)
        if repo is None:
            return CodingResult(success=False, summary="No repo", error="missing repo path")

        if not await self.healthcheck():
            logger.warning("Cursor CLI not found — using mock adapter")
            return await self._fallback.run_task(plan, context, branch)

        checkout_branch(repo, branch)
        prompt = (
            f"Implement: {plan.summary}. "
            f"Touch files: {', '.join(plan.files_to_touch[:10])}. "
            f"Tests: {plan.test_strategy}"
        )
        cmd = ["cursor-agent", "run", "--prompt", prompt, "--cwd", str(repo)]
        if not command_available("cursor-agent"):
            cmd = ["cursor", "agent", "--prompt", prompt]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return CodingResult(
                success=False,
                summary="Cursor agent failed",
                error=(stderr or stdout).decode()[:500],
            )

        return CodingResult(
            success=True,
            summary=f"Cursor completed task on {branch}",
            files_changed=plan.files_to_touch,
            commits_ahead=commits_ahead(repo, branch),
        )
