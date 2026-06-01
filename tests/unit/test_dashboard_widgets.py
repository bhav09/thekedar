"""Dashboard widget schema smoke tests."""

import pytest
from fastapi.testclient import TestClient
from thekedar_dashboard_hub.app import create_app
from thekedar_shared.settings import get_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]) -> TestClient:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        c.auth_headers = auth_headers
        yield c
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "path",
    [
        "active-runs",
        "pending-approvals",
        "workstation-health",
        "ticket-code",
        "pr-pipeline",
        "cost-summary",
        "audit-trail",
        "messaging-activity",
        "slack-app-home",
        "workspaces",
    ],
)
def test_widget_endpoints(client: TestClient, path: str) -> None:
    resp = client.get(f"/api/v1/widgets/{path}", headers=client.auth_headers)
    assert resp.status_code == 200
    assert "widget" in resp.json()


def test_update_settings(client: TestClient) -> None:
    # Seed workspace first
    from thekedar_shared.db import Workspace
    session = client.app.state.session_factory()
    ws = session.query(Workspace).filter_by(tenant_id="default").first()
    if not ws:
        session.add(Workspace(tenant_id="default", name="Default Workspace"))
        session.commit()
    session.close()

    payload = {"github_project_url": "https://github.com/bhav66d/thekedar", "jira_project_key": "THE-NEW"}
    resp = client.post("/api/v1/widgets/workspaces/settings", json=payload, headers=client.auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert resp.json()["workspace"]["github_project_url"] == "https://github.com/bhav66d/thekedar"
    assert resp.json()["workspace"]["jira_project_key"] == "THE-NEW"
