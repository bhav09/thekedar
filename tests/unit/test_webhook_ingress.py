"""Webhook ingress tests with mocked Redis."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from thekedar_webhook_ingress.app import create_app
from thekedar_webhook_ingress.deps import get_redis


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_slack_url_verification(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/slack",
            json={"type": "url_verification", "challenge": "challenge-token"},
        )
    assert response.status_code == 200
    assert response.json()["challenge"] == "challenge-token"


@pytest.mark.asyncio
async def test_slack_event_enqueued(app) -> None:
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.lpush = AsyncMock(return_value=1)

    async def _redis_override() -> AsyncGenerator[AsyncMock, None]:
        yield mock_redis

    app.dependency_overrides[get_redis] = _redis_override

    payload = {
        "team_id": "T001",
        "event": {
            "type": "message",
            "user": "U1",
            "text": "Hello @Architect",
            "channel": "C1",
            "ts": "999.1",
        },
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhooks/slack", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_redis.set.assert_called()
    mock_redis.lpush.assert_called()


@pytest.mark.asyncio
async def test_idempotency_claim_before_publish(app) -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(side_effect=[True, False])
    mock_redis.lpush = AsyncMock(return_value=1)

    async def _redis_override() -> AsyncGenerator[AsyncMock, None]:
        yield mock_redis

    app.dependency_overrides[get_redis] = _redis_override

    payload = {
        "team_id": "T001",
        "event": {
            "type": "message",
            "user": "U1",
            "text": "Hello @Architect",
            "channel": "C1",
            "ts": "999.1",
        },
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post("/webhooks/slack", json=payload)
        resp2 = await client.post("/webhooks/slack", json=payload)

    app.dependency_overrides.clear()
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert mock_redis.lpush.call_count == 1
