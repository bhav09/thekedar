"""Claude Code CLI adapter."""

from __future__ import annotations

import asyncio
import logging

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, command_available, repo_path
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_ide_adapters.prompt import build_ide_prompt, post_run_metrics
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fallback = MockIDEAdapter(settings)

    async def healthcheck(self) -> bool:
        return command_available("claude")

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        repo = repo_path(self._settings, tenant_id=context.tenant_id, repo=context.repo)
        if repo is None:
            return CodingResult(success=False, summary="No repo", error="missing repo path")

        if not await self.healthcheck():
            if self._settings.environment in ("staging", "prod"):
                raise ConfigurationError("Claude Code CLI not found — mock adapter fallback blocked in staging/prod")
            logger.warning("Claude Code CLI not found — using mock adapter")
            return await self._fallback.run_task(plan, context, branch)

        checkout_branch(repo, branch)
        prompt = build_ide_prompt(plan, context, branch)
        
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            "Edit,Write,Bash",
            cwd=str(repo),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            # 30 minute timeout limit
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return CodingResult(success=False, summary="Claude Code execution timed out", error="30 minute timeout exceeded")

        if proc.returncode != 0:
            return CodingResult(
                success=False,
                summary="Claude Code failed",
                error=(stderr or stdout).decode(errors="replace")[:500],
            )

        return post_run_metrics(repo, branch, success=True, summary=f"Claude Code completed on {branch}")
