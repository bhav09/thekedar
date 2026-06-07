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


def test_resolve_pending_approval_requires_uuid(orchestrator_services, session_factory) -> None:
    from thekedar_shared.schemas import Channel, MessageEvent
    from thekedar_shared.db import PendingApproval

    session = session_factory()
    session.add(
        PendingApproval(
            id="ap-uuid-12345",
            tenant_id="default",
            approval_type="impact_review",
            summary="Test approval",
            status="pending",
        )
    )
    session.commit()
    session.close()

    msg = MessageEvent(
        channel=Channel.SLACK,
        message_id="m1",
        thread_id="C1",
        user_id="U1",
        tenant_id="T001",
        text="approve",
        idempotency_key="k1",
    )

    # Resolve without uuid -> must return None
    res = orchestrator_services.resolve_pending_approval(msg, None)
    assert res is None

    # Resolve with correct uuid -> must return the approval
    res_with_uuid = orchestrator_services.resolve_pending_approval(msg, "ap-uuid-12345")
    assert res_with_uuid is not None
    assert res_with_uuid.id == "ap-uuid-12345"
