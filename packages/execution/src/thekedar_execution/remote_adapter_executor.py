"""Remote adapter executor — executes IDE coding adapters on the remote workstation."""

from __future__ import annotations

import base64
import logging
from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import CodingResult
from thekedar_execution.remote import RemoteExecutor
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class RemoteAdapterExecutor:
    """Executes coding adapters remotely on GCP Cloud Workstations."""

    def __init__(self, settings: Settings, remote_executor: RemoteExecutor) -> None:
        self._settings = settings
        self._remote = remote_executor

    async def run_coding(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str, adapter_name: str
    ) -> CodingResult:
        repo_mount = self._remote.repo_mount_path(context.tenant_id, context.repo)

        # Build the IDE prompt
        from thekedar_ide_adapters.prompt import build_ide_prompt
        prompt = build_ide_prompt(plan, context, branch)

        # Write prompt to remote workstation VM safely using base64
        encoded_prompt = base64.b64encode(prompt.encode("utf-8")).decode("utf-8")
        write_cmd = ["bash", "-c", f"echo '{encoded_prompt}' | base64 -d > .thekedar_prompt.txt"]
        write_res = await self._remote.run_command(
            context.tenant_id, write_cmd, cwd=repo_mount, timeout_s=30
        )
        if write_res.exit_code != 0:
            return CodingResult(
                success=False,
                summary="Failed to write prompt file to remote VM",
                error=write_res.stderr or write_res.stdout,
            )

        # Construct command based on adapter name
        name = adapter_name.lower()
        if name == "auto":
            probe_res = await self._remote.run_command(
                context.tenant_id,
                ["bash", "-c", "if command -v claude >/dev/null 2>&1; then echo 'claude'; elif command -v agy >/dev/null 2>&1; then echo 'antigravity'; else echo 'antigravity'; fi"],
                cwd=repo_mount,
                timeout_s=10,
            )
            if probe_res.exit_code == 0 and probe_res.stdout.strip():
                name = probe_res.stdout.strip().lower()
            else:
                name = "antigravity"

        if name == "claude":
            cmd = ["bash", "-c", "claude -p \"$(cat .thekedar_prompt.txt)\" --allowedTools Edit,Write,Bash"]
        elif name in ("antigravity", "agy"):
            cmd = ["bash", "-c", "agy run --prompt \"$(cat .thekedar_prompt.txt)\""]
        elif name == "cursor":
            cmd = [
                "bash",
                "-c",
                "if command -v cursor-agent >/dev/null 2>&1; then cursor-agent run --prompt \"$(cat .thekedar_prompt.txt)\" --cwd .; else cursor agent --prompt \"$(cat .thekedar_prompt.txt)\"; fi",
            ]
        else:
            # Fallback / unsupported remote adapters default to agy/antigravity or raise ConfigurationError in prod
            from thekedar_shared.exceptions import ConfigurationError
            if self._settings.environment in ("staging", "prod"):
                raise ConfigurationError(f"Adapter '{adapter_name}' is not supported for remote execution in staging/prod")
            # For development fall back to antigravity
            cmd = ["bash", "-c", "agy run --prompt \"$(cat .thekedar_prompt.txt)\""]

        logger.info("Executing remote adapter %s command on workstation", name)
        # Execute the adapter remotely (30 minute timeout limit = 1800s)
        exec_res = await self._remote.run_command(
            context.tenant_id, cmd, cwd=repo_mount, timeout_s=1800
        )

        if exec_res.exit_code != 0:
            # Cleanup prompt file even on failure
            await self._remote.run_command(
                context.tenant_id, ["rm", "-f", ".thekedar_prompt.txt"], cwd=repo_mount, timeout_s=10
            )
            return CodingResult(
                success=False,
                summary=f"Remote adapter {name} failed",
                error=exec_res.stderr or exec_res.stdout,
            )

        # Fetch files changed relative to origin/main or main
        diff_res = await self._remote.run_command(
            context.tenant_id,
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=repo_mount,
            timeout_s=30,
        )
        if diff_res.exit_code != 0:
            diff_res = await self._remote.run_command(
                context.tenant_id,
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=repo_mount,
                timeout_s=30,
            )

        files_changed = []
        if diff_res.exit_code == 0:
            files_changed = [line.strip() for line in diff_res.stdout.splitlines() if line.strip()]

        # Fetch commits ahead
        commits_res = await self._remote.run_command(
            context.tenant_id,
            ["git", "rev-list", "--count", f"origin/main..{branch}"],
            cwd=repo_mount,
            timeout_s=30,
        )
        if commits_res.exit_code != 0:
            commits_res = await self._remote.run_command(
                context.tenant_id,
                ["git", "rev-list", "--count", f"main..{branch}"],
                cwd=repo_mount,
                timeout_s=30,
            )

        commits_ahead = 0
        if commits_res.exit_code == 0:
            try:
                commits_ahead = int(commits_res.stdout.strip())
            except ValueError:
                pass

        # Cleanup prompt file
        await self._remote.run_command(
            context.tenant_id, ["rm", "-f", ".thekedar_prompt.txt"], cwd=repo_mount, timeout_s=10
        )

        return CodingResult(
            success=True,
            summary=f"Remote adapter {name} completed on {branch}",
            files_changed=files_changed,
            commits_ahead=commits_ahead,
        )
