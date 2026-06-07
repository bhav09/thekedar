"""Execution router — Cloud Workstation vs local IDE."""

from __future__ import annotations

from typing import Protocol

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters import CodingResult
from thekedar_shared.db import Workspace
from thekedar_shared.settings import Settings

from thekedar_execution.cloud import CloudWorkstationExecutor, WorkstationOps
from thekedar_execution.local import LocalIDEExecutor


class ExecutionUnavailable(Exception):
    pass


class Executor(Protocol):
    async def run_coding(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str, run_id: str
    ) -> CodingResult: ...

    async def run_tests(self, tenant_id: str, run_id: str | None) -> tuple[str, str]: ...


class ExecutionRouter:
    def __init__(self, settings: Settings, workstation_ops: WorkstationOps | None = None) -> None:
        self._settings = settings
        self._cloud = (
            CloudWorkstationExecutor(settings, workstation_ops)
            if workstation_ops is not None
            else None
        )
        self._local = LocalIDEExecutor(settings)

    def select(self, workspace: Workspace) -> Executor:
        if (
            self._cloud is not None
            and self._settings.environment in ("staging", "prod")
            and workspace.cloud_workstation_config_id
            and self._settings.gcp_project_id
        ):
            return self._cloud
        if self._settings.local_ide_enabled or self._settings.demo_mode:
            return self._local
        if self._settings.local_repo_path:
            return self._local
        if self._cloud is not None and self._settings.gcp_project_id:
            return self._cloud
        raise ExecutionUnavailable(
            "No execution plane available. Enable THEKEDAR_LOCAL_IDE or configure Cloud Workstation."
        )
