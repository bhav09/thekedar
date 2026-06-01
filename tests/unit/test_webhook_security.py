"""Webhook signature enforcement tests."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from thekedar_shared.settings import get_settings
from thekedar_webhook_ingress.app import create_app
from thekedar_webhook_ingress.deps import get_redis


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE", "true")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    yield create_app()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_unsigned_slack_rejected_when_required(app) -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.lpush = AsyncMock(return_value=1)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)

    async def _redis_override():
        yield mock_redis

    app.dependency_overrides[get_redis] = _redis_override

    payload = {
        "team_id": "T001",
        "event": {
            "type": "message",
            "user": "U1",
            "text": "hi",
            "channel": "C1",
            "ts": "1.1",
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhooks/slack", json=payload)
    assert response.status_code == 500
    app.dependency_overrides.clear()
