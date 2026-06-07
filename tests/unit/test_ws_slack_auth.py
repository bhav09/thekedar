"""Tests for WebSocket authentication and Slack interactive workspace binding."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from thekedar_shared.auth import create_access_token
from thekedar_shared.settings import get_settings
from thekedar_dashboard_hub.app import create_app as create_dashboard_app
from thekedar_webhook_ingress.app import create_app as create_ingress_app


def test_websocket_auth_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    with TestClient(create_dashboard_app()) as client:
        # Code 4001 is expected for missing token
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/events") as websocket:
                pass


def test_websocket_auth_accepts_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    settings = get_settings()
    token = create_access_token(settings, tenant_id="default")
    with TestClient(create_dashboard_app()) as client:
        with client.websocket_connect(f"/ws/events?token={token}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "heartbeat"
            assert data["tenant_id"] == "default"


def test_slack_interactive_workspace_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()

    with TestClient(create_ingress_app()) as client:
        session = client.app.state.session_factory()
        from thekedar_shared.db import Workspace, PendingApproval
        session.add(
            Workspace(
                tenant_id="tenant-a",
                name="Tenant A Workspace",
                slack_team_id="T12345",
            )
        )
        session.add(
            PendingApproval(
                id="ap-1",
                tenant_id="tenant-a",
                approval_type="impact_review",
                summary="Test approval",
                status="pending",
            )
        )
        session.commit()
        session.close()

        # Workspace mismatch
        body = {
            "payload": json.dumps({
                "type": "block_actions",
                "team": {"id": "T54321"},
                "actions": [{"action_id": "approve_action", "value": "ap-1"}],
                "user": {"id": "U1"},
            })
        }
        resp = client.post("/webhooks/slack/interactive", data=body)
        assert resp.status_code == 200
        assert "Workspace mismatch" in resp.text

        # Valid binding
        body_valid = {
            "payload": json.dumps({
                "type": "block_actions",
                "team": {"id": "T12345"},
                "actions": [{"action_id": "approve_action", "value": "ap-1"}],
                "user": {"id": "U1"},
            })
        }
        resp_valid = client.post("/webhooks/slack/interactive", data=body_valid)
        assert resp_valid.status_code == 200
        assert "approved" in resp_valid.text
