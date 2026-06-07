"""VS Code Remote / CLI adapter."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, command_available, repo_path
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_ide_adapters.prompt import build_ide_prompt
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError

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
        repo = repo_path(self._settings, tenant_id=context.tenant_id, repo=context.repo)
        if repo is None:
            return CodingResult(success=False, summary="No repo", error="missing repo path")

        task_mode = getattr(self._settings, "vscode_task_mode", "disabled").lower()
        if task_mode == "extension":
            logger.info("Enqueuing VS Code task for tenant %s, branch %s", context.tenant_id, branch)
            from thekedar_shared.db import init_db
            from sqlalchemy import text
            import json

            session_factory = init_db(self._settings.database_url)
            session = session_factory()
            task_id = None
            table_exists = False
            try:
                # Check if the ide_tasks table exists in DB (to prevent crash before Phase D schema is migrated)
                # Engine-agnostic check: simply try executing SELECT 1 LIMIT 1
                try:
                    session.execute(text("SELECT 1 FROM ide_tasks LIMIT 1"))
                    table_exists = True
                except Exception:
                    table_exists = False

                if table_exists:
                    from uuid import uuid4
                    task_id = str(uuid4())
                    from thekedar_context.context_pack import ContextPackBuilder
                    context_pack = ContextPackBuilder.build_context_pack(context, [plan.summary])
                    payload = {
                        "plan": plan.model_dump(),
                        "context_pack": context_pack,
                    }
                    from datetime import datetime, UTC
                    session.execute(
                        text("INSERT INTO ide_tasks (id, tenant_id, run_id, status, payload_json, created_at) VALUES (:id, :tenant_id, :run_id, :status, :payload_json, :created_at)"),
                        {
                            "id": task_id,
                            "tenant_id": context.tenant_id,
                            "run_id": context.snapshot_id,
                            "status": "pending",
                            "payload_json": json.dumps(payload),
                            "created_at": datetime.now(UTC),
                        }
                    )
                    session.commit()
                else:
                    logger.warning("ide_tasks table does not exist yet (Phase D migration pending)")
            except Exception as e:
                logger.error("Failed to enqueue VS Code task: %s", e)
            finally:
                session.close()

            if task_id:
                timeout = int(getattr(self._settings, "vscode_task_timeout_s", 1800))
                elapsed = 0
                while elapsed < timeout:
                    await asyncio.sleep(5)
                    elapsed += 5
                    session = session_factory()
                    try:
                        res = session.execute(
                            text("SELECT status, result_json FROM ide_tasks WHERE id = :id"),
                            {"id": task_id}
                        ).first()
                        if res:
                            status, result_json = res
                            if status == "completed":
                                result_data = json.loads(result_json or "{}")
                                return CodingResult(
                                    success=True,
                                    summary=result_data.get("summary", "VS Code task completed successfully"),
                                    files_changed=result_data.get("files_changed", []),
                                    commits_ahead=result_data.get("commits_ahead", 1),
                                )
                            elif status == "failed":
                                result_data = json.loads(result_json or "{}")
                                return CodingResult(
                                    success=False,
                                    summary="VS Code task failed",
                                    error=result_data.get("error", "Task reported failure"),
                                )
                    except Exception as e:
                        logger.error("Error polling VS Code task: %s", e)
                    finally:
                        session.close()
                return CodingResult(success=False, summary="VS Code task timed out", error=f"Timeout of {timeout}s exceeded")
            else:
                return CodingResult(
                    success=False,
                    summary="Failed to queue VS Code task",
                    error="VS Code extension mode active but ide_tasks table does not exist or task could not be enqueued",
                )

        if not await self.healthcheck():
            if self._settings.environment in ("staging", "prod"):
                raise ConfigurationError("VS Code CLI/server not found — mock adapter fallback blocked in staging/prod")
            logger.warning("VS Code CLI/server not found — using mock adapter")
            return await self._fallback.run_task(plan, context, branch)

        checkout_branch(repo, branch)
        prompt = build_ide_prompt(plan, context, branch)
        prompt_file = repo / ".thekedar_prompt.txt"
        prompt_file.write_text(prompt)

        return CodingResult(
            success=False,
            summary="VS Code task queued. Direct CLI mode does not support automatic editing. Use the VS Code extension or Remote-SSH.",
            error="Direct CLI coding edit not supported. Enable THEKEDAR_VSCODE_TASK_MODE=extension to poll task",
        )
