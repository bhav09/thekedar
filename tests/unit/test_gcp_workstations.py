"""Unit tests for GCP Workstations client and remote executor."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, AsyncMock

# Mock google.cloud.workstations_v1 before importing any other modules
mock_workstations_v1 = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.workstations_v1"] = mock_workstations_v1

import asyncio
import pytest

from thekedar_shared.settings import Settings
from thekedar_execution.gcp_workstations import GcpWorkstationClient
from thekedar_execution.remote import GcpWorkstationRemoteExecutor, CommandResult


class MockWorkstation:
    def __init__(self, host: str, uid: str, state_name: str) -> None:
        self.host = host
        self.uid = uid
        self.state = MagicMock()
        self.state.name = state_name


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "test-proj")
    monkeypatch.setenv("GCP_REGION", "us-east1")
    monkeypatch.setenv("GCP_WORKSTATION_CLUSTER_ID", "test-cluster")
    monkeypatch.setenv("GCP_WORKSTATION_CONFIG_ID", "test-config")


@pytest.mark.asyncio
async def test_gcp_workstation_client_state_and_start(monkeypatch) -> None:
    settings = Settings()
    client = GcpWorkstationClient(settings)

    # Mock WorkstationsClient and its methods
    mock_client_instance = MagicMock()
    mock_workstation = MockWorkstation(host="workstation-host.com", uid="uid-123", state_name="STATE_STOPPED")
    mock_client_instance.get_workstation.return_value = mock_workstation

    mock_operation = MagicMock()
    mock_operation.result.return_value = None
    mock_client_instance.start_workstation.return_value = mock_operation
    mock_client_instance.stop_workstation.return_value = mock_operation

    # Monkeypatch the import/initialization
    monkeypatch.setattr(client, "_get_client", lambda: mock_client_instance)

    # Test resource name construction
    res_name = client.get_workstation_resource_name("tenant_abc", None)
    assert res_name == "projects/test-proj/locations/us-east1/workstationClusters/test-cluster/workstationConfigs/test-config/workstations/thekedar-ws-tenant-abc"

    # Test state retrieval
    state = await client.get_state("tenant_abc", None)
    assert state == "STATE_STOPPED"
    mock_client_instance.get_workstation.assert_called_with(name=res_name)

    # Test starting the workstation
    await client.start("tenant_abc", None)
    assert mock_client_instance.start_workstation.called

    # Test stopping the workstation
    await client.stop("tenant_abc", None)
    assert mock_client_instance.stop_workstation.called


@pytest.mark.asyncio
async def test_gcp_workstation_executor_ensure_ready(monkeypatch) -> None:
    settings = Settings()
    executor = GcpWorkstationRemoteExecutor(settings)

    # Mock the GcpWorkstationClient
    mock_gcp_client = MagicMock()
    mock_gcp_client.get_state = AsyncMock(return_value="STATE_STOPPED")
    mock_gcp_client.start = AsyncMock()
    mock_gcp_client.get_workstation_resource_name = MagicMock(return_value="full-resource-name")

    # Mock the underlying WorkstationsClient for get_workstation call
    mock_client_api = MagicMock()
    mock_workstation = MockWorkstation(host="resolved-host.com", uid="instance-uid-456", state_name="STATE_RUNNING")
    mock_client_api.get_workstation.return_value = mock_workstation
    mock_gcp_client._get_client.return_value = mock_client_api

    monkeypatch.setattr("thekedar_execution.gcp_workstations.GcpWorkstationClient", lambda s: mock_gcp_client)

    endpoint = await executor.ensure_ready("tenant-1", None)
    assert endpoint.host == "resolved-host.com"
    assert endpoint.instance_id == "instance-uid-456"

    mock_gcp_client.get_state.assert_called_once_with("tenant-1", None)
    mock_gcp_client.start.assert_called_once_with("tenant-1", None)


@pytest.mark.asyncio
async def test_gcp_workstation_executor_run_command(monkeypatch) -> None:
    settings = Settings()
    executor = GcpWorkstationRemoteExecutor(settings)

    captured_args = []
    async def mock_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"mock stdout", b"mock stderr")
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_create_subprocess_exec)

    res = await executor.run_command("tenant-abc", ["ls", "-l"], "/tmp", timeout_s=30)
    assert res.exit_code == 0
    assert res.stdout == "mock stdout"
    assert res.stderr == "mock stderr"

    # Verify that gcloud workstations ssh was called with correct parameters
    assert "gcloud" in captured_args
    assert "workstations" in captured_args
    assert "ssh" in captured_args
    assert "thekedar-ws-tenant-abc" in captured_args
    assert "--project" in captured_args
    assert "test-proj" in captured_args
    assert "cd /tmp && ls -l" in captured_args
