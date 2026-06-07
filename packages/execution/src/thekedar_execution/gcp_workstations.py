"""GCP Workstations client wrapper using google-cloud-workstations SDK."""

from __future__ import annotations

import logging
import asyncio
from typing import Any
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class GcpWorkstationClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _get_client(self) -> Any:
        from google.cloud import workstations_v1
        return workstations_v1.WorkstationsClient()

    def get_workstation_resource_name(self, tenant_id: str, config_id: str | None) -> str:
        project = self._settings.gcp_project_id or "mock-project"
        location = self._settings.gcp_region or "us-central1"
        cluster = self._settings.gcp_workstation_cluster_id or "mock-cluster"
        config = config_id or self._settings.gcp_workstation_config_id or "mock-config"

        # Sanitize tenant_id for GCP resource name (lowercase alphanumeric + hyphens)
        clean_tenant = "".join(c.lower() if c.isalnum() else "-" for c in tenant_id)
        clean_tenant = clean_tenant.strip("-")
        workstation_id = f"thekedar-ws-{clean_tenant}"

        return f"projects/{project}/locations/{location}/workstationClusters/{cluster}/workstationConfigs/{config}/workstations/{workstation_id}"

    async def get_state(self, tenant_id: str, config_id: str | None) -> str:
        """Returns STATE_RUNNING, STATE_STARTING, STATE_STOPPED, or STATE_UNSPECIFIED."""
        try:
            from google.cloud import workstations_v1
            client = self._get_client()
            name = self.get_workstation_resource_name(tenant_id, config_id)

            loop = asyncio.get_running_loop()
            workstation = await loop.run_in_executor(
                None, lambda: client.get_workstation(name=name)
            )
            state_enum = workstation.state
            return state_enum.name
        except Exception as e:
            logger.warning("Failed to get workstation state for %s: %s", tenant_id, e)
            return "STATE_STOPPED"

    async def start(self, tenant_id: str, config_id: str | None) -> Any:
        """Starts the workstation and waits for operation completion."""
        try:
            from google.cloud import workstations_v1
            client = self._get_client()
            name = self.get_workstation_resource_name(tenant_id, config_id)

            logger.info("Starting GCP workstation: %s", name)
            request = workstations_v1.StartWorkstationRequest(name=name)

            loop = asyncio.get_running_loop()
            operation = await loop.run_in_executor(
                None, lambda: client.start_workstation(request=request)
            )

            logger.info("Waiting for workstation start operation to complete: %s", name)
            await loop.run_in_executor(
                None, lambda: operation.result(timeout=90)
            )
            logger.info("Workstation started successfully: %s", name)
        except Exception as e:
            logger.error("Failed to start GCP workstation for %s: %s", tenant_id, e)
            raise RuntimeError(f"GCP Workstation start failed: {str(e)}") from e

    async def stop(self, tenant_id: str, config_id: str | None) -> Any:
        """Stops/hibernates the workstation."""
        try:
            from google.cloud import workstations_v1
            client = self._get_client()
            name = self.get_workstation_resource_name(tenant_id, config_id)

            logger.info("Stopping GCP workstation: %s", name)
            request = workstations_v1.StopWorkstationRequest(name=name)

            loop = asyncio.get_running_loop()
            operation = await loop.run_in_executor(
                None, lambda: client.stop_workstation(request=request)
            )

            logger.info("Waiting for workstation stop operation to complete: %s", name)
            await loop.run_in_executor(
                None, lambda: operation.result(timeout=90)
            )
            logger.info("Workstation stopped successfully: %s", name)
        except Exception as e:
            logger.error("Failed to stop GCP workstation for %s: %s", tenant_id, e)
            raise RuntimeError(f"GCP Workstation stop failed: {str(e)}") from e
