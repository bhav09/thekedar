"""Dashboard approval API tests."""

import pytest
from fastapi.testclient import TestClient
from thekedar_dashboard_hub.app import create_app
from thekedar_shared.auth import create_access_token
from thekedar_shared.db import PendingApproval
from thekedar_shared.settings import get_settings


@pytest.fixture
def dashboard_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_approval_flow(dashboard_client: TestClient, auth_headers: dict[str, str]) -> None:
    session = dashboard_client.app.state.session_factory()
    approval = PendingApproval(
        id="ap-1",
        tenant_id="default",
        approval_type="merge_pr",
        summary="Merge THE-42",
        status="pending",
    )
    session.add(approval)
    session.commit()
    session.close()

    resp = dashboard_client.get("/api/v1/approvals/ap-1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    resp = dashboard_client.post("/api/v1/approvals/ap-1/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_approval_requires_auth(dashboard_client: TestClient) -> None:
    resp = dashboard_client.get("/api/v1/approvals/ap-1")
    assert resp.status_code == 401


def test_approval_tenant_isolation(dashboard_client: TestClient) -> None:
    settings = get_settings()
    other_headers = {
        "Authorization": f"Bearer {create_access_token(settings, tenant_id='other')}"
    }
    session = dashboard_client.app.state.session_factory()
    session.add(
        PendingApproval(
            id="ap-2",
            tenant_id="default",
            approval_type="merge_pr",
            summary="Secret",
            status="pending",
        )
    )
    session.commit()
    session.close()

    resp = dashboard_client.get("/api/v1/approvals/ap-2", headers=other_headers)
    assert resp.status_code == 404
