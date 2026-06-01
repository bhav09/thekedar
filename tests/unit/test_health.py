"""Health endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from thekedar_webhook_ingress.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_ok(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "webhook-ingress"
    assert response.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_ready_returns_ready(app, monkeypatch) -> None:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    from thekedar_shared.settings import get_settings

    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_correlation_id_propagated(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-Id": "test-correlation-123"})
    assert response.headers.get("x-request-id") == "test-correlation-123"
