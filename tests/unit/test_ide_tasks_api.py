"""Unit tests for the IDE Tasks API endpoints."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from thekedar_shared.settings import Settings, get_settings
from thekedar_shared.db import Workspace, IdeTask, init_db
from thekedar_shared.auth import create_access_token
from thekedar_dashboard_hub.app import create_app


@pytest.fixture
def app_and_client(session_factory, test_settings: Settings, monkeypatch):
    test_settings.database_url = "sqlite:///:memory:"
    test_settings.jwt_secret = SecretStr("test-secret-with-at-least-32-bytes-of-key-length!!")
    
    app = create_app()
    app.state.session_factory = session_factory
    
    # Override get_settings dependency so the router uses our test_settings
    app.dependency_overrides[get_settings] = lambda: test_settings
    
    client = TestClient(app)
    return app, client


def test_ide_tasks_lifecycle(session_factory, app_and_client, test_settings: Settings) -> None:
    _, client = app_and_client

    # Get authorized tokens
    token_tenant_a = create_access_token(test_settings, tenant_id="tenant-a")
    headers_a = {"Authorization": f"Bearer {token_tenant_a}"}

    token_tenant_b = create_access_token(test_settings, tenant_id="tenant-b")
    headers_b = {"Authorization": f"Bearer {token_tenant_b}"}

    # 1. Create task for tenant-a
    payload = {"plan_summary": "Update readme"}
    response = client.post(
        "/api/v1/ide-tasks",
        headers=headers_a,
        json={
            "run_id": "run-a",
            "payload_json": json.dumps(payload),
        }
    )
    assert response.status_code == 200
    task_id = response.json()["id"]
    assert task_id

    # 2. Verify tenant isolation - tenant-b should see 0 pending tasks
    pending_resp_b = client.get("/api/v1/ide-tasks/pending", headers=headers_b)
    assert pending_resp_b.status_code == 200
    assert len(pending_resp_b.json()) == 0

    # 3. Tenant-a should see 1 pending task
    pending_resp_a = client.get("/api/v1/ide-tasks/pending", headers=headers_a)
    assert pending_resp_a.status_code == 200
    assert len(pending_resp_a.json()) == 1
    assert pending_resp_a.json()[0]["id"] == task_id

    # 4. Claim the task
    claim_resp = client.post(
        f"/api/v1/ide-tasks/{task_id}/claim",
        headers=headers_a,
        json={"claimed_by": "vscode-extension"}
    )
    assert claim_resp.status_code == 200
    assert claim_resp.json()["status"] == "claimed"

    # 5. Complete the task
    result = {"success": True, "files_changed": ["README.md"]}
    complete_resp = client.post(
        f"/api/v1/ide-tasks/{task_id}/complete",
        headers=headers_a,
        json={"result_json": json.dumps(result)}
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    # 6. Verify task status in database
    session = session_factory()
    task = session.get(IdeTask, task_id)
    assert task.status == "completed"
    assert json.loads(task.result_json)["success"] is True
    session.close()
