"""Cloud Workstation executor — GCP API with remote execution."""

from __future__ import annotations

import logging
from typing import Protocol

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import CodingResult, select_adapter
from thekedar_shared.settings import Settings
from thekedar_execution.remote import select_remote_executor

logger = logging.getLogger(__name__)


class WorkstationOps(Protocol):
    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> object: ...

    async def sync_repo_and_test(self, tenant_id: str, run_id: str | None) -> object: ...


class CloudWorkstationExecutor:
    def __init__(self, settings: Settings, workstation: WorkstationOps) -> None:
        self._settings = settings
        self._workstation = workstation
        self._remote = select_remote_executor(settings)

    async def run_coding(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str, run_id: str
    ) -> CodingResult:
        # Resolve config_id from Workspace database row
        from thekedar_shared.db import init_db, Workspace
        session_factory = init_db(self._settings.database_url)
        session = session_factory()
        config_id = None
        try:
            workspace = session.query(Workspace).filter_by(tenant_id=context.tenant_id).first()
            if workspace:
                config_id = workspace.cloud_workstation_config_id
        finally:
            session.close()

        # Ensure workstation is ready
        await self._workstation.ensure_ready(context.tenant_id, config_id)

        # Sync repo to remote workstation filesystem before adapter executes
        logger.info("Syncing remote repo %s to branch %s", context.repo, branch)
        sync_res = await self._remote.sync_repo(context.tenant_id, context.repo, branch)
        if not sync_res.success:
            return CodingResult(success=False, summary=f"Sync failed: {sync_res.summary}")

        # Execute coding via selected adapter
        adapter = select_adapter(self._settings)
        return await adapter.run_task(plan, context, branch)

    async def run_tests(self, tenant_id: str, run_id: str | None) -> tuple[str, str]:
        record = await self._workstation.sync_repo_and_test(tenant_id, run_id)
        return str(record.status), str(record.summary)
