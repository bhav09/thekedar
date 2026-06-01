"""Dashboard JWT auth and tenant isolation."""

import pytest
from fastapi.testclient import TestClient
from thekedar_dashboard_hub.app import create_app
from thekedar_shared.db import AgentRun
from thekedar_shared.settings import get_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_widgets_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/widgets/active-runs").status_code == 401


def test_widgets_tenant_scoped(client: TestClient, auth_headers: dict[str, str]) -> None:
    session = client.app.state.session_factory()
    session.add(
        AgentRun(
            id="r1",
            tenant_id="default",
            channel="slack",
            user_id="u1",
            workflow="architect",
            status="running",
            trigger_text="hello",
        )
    )
    session.add(
        AgentRun(
            id="r2",
            tenant_id="other",
            channel="slack",
            user_id="u2",
            workflow="coder",
            status="running",
            trigger_text="secret",
        )
    )
    session.commit()
    session.close()

    resp = client.get("/api/v1/widgets/active-runs", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["run_id"] == "r1"


def test_auth_token_endpoint(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/token", json={"tenant_id": "default"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
