"""Cloud Workstation executor — GCP API with local simulation fallback."""

from __future__ import annotations

import logging
from typing import Protocol

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import CodingResult, select_adapter
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class WorkstationOps(Protocol):
    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> object: ...

    async def sync_repo_and_test(self, tenant_id: str, run_id: str | None) -> object: ...


class CloudWorkstationExecutor:
    def __init__(self, settings: Settings, workstation: WorkstationOps) -> None:
        self._settings = settings
        self._workstation = workstation

    async def run_coding(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str, run_id: str
    ) -> CodingResult:
        await self._workstation.ensure_ready(context.tenant_id, None)
        adapter = select_adapter(self._settings)
        return await adapter.run_task(plan, context, branch)

    async def run_tests(self, tenant_id: str, run_id: str | None) -> tuple[str, str]:
        record = await self._workstation.sync_repo_and_test(tenant_id, run_id)
        return str(record.status), str(record.summary)
