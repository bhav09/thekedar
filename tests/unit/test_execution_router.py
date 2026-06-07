"""Unit tests for ExecutionRouter logic."""

from __future__ import annotations

import pytest
from thekedar_shared.db import Workspace
from thekedar_shared.settings import Settings
from thekedar_execution.router import ExecutionRouter, ExecutionUnavailable
from thekedar_execution.cloud import CloudWorkstationExecutor
from thekedar_execution.local import LocalIDEExecutor


class DummyWorkstationOps:
    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> object:
        return None

    async def sync_repo_and_test(self, tenant_id: str, run_id: str | None) -> object:
        return None


def test_execution_router_selection(test_settings: Settings) -> None:
    ops = DummyWorkstationOps()
    router = ExecutionRouter(test_settings, ops)

    workspace = Workspace(
        tenant_id="tenant1",
        name="test",
        cloud_workstation_config_id="config-1",
    )

    # 1. Dev / local fallback mode
    test_settings.environment = "local"
    test_settings.local_ide_enabled = True
    test_settings.gcp_project_id = None
    executor = router.select(workspace)
    assert isinstance(executor, LocalIDEExecutor)

    # 2. Deployed staging / prod with config
    test_settings.environment = "staging"
    test_settings.local_ide_enabled = False
    test_settings.gcp_project_id = "test-gcp-project"
    test_settings.llm_provider = "openai" # must not be mock in staging/prod
    executor = router.select(workspace)
    assert isinstance(executor, CloudWorkstationExecutor)

    # 3. No workstation config nor local setup in staging/prod
    workspace.cloud_workstation_config_id = None
    test_settings.local_ide_enabled = False
    test_settings.local_repo_path = None
    test_settings.gcp_project_id = None
    test_settings.demo_mode = False
    with pytest.raises(ExecutionUnavailable):
        router.select(workspace)
