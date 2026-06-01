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
    ],
)
def test_widget_endpoints(client: TestClient, path: str) -> None:
    resp = client.get(f"/api/v1/widgets/{path}", headers=client.auth_headers)
    assert resp.status_code == 200
    assert "widget" in resp.json()
