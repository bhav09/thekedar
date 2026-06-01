"""GitHub webhook tests."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from thekedar_shared.db import TicketCodeLink
from thekedar_shared.settings import get_settings
from thekedar_webhook_ingress.app import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("THEKEDAR_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("THEKEDAR_DEMO_MODE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_github_webhook_updates_ci(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()

    session = client.app.state.session_factory()
    session.add(
        TicketCodeLink(tenant_id="default", issue_key="THE-1", pr_number=42, ci_status="pending")
    )
    session.commit()
    session.close()

    body = json.dumps(
        {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "html_url": "https://github.com/o/r/pull/42",
                "head": {"ref": "b"},
            },
            "repository": {"full_name": "o/r"},
        }
    ).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig},
    )
    assert resp.status_code == 200

    session = client.app.state.session_factory()
    link = session.query(TicketCodeLink).filter_by(issue_key="THE-1").first()
    assert link is not None
    assert link.pr_url == "https://github.com/o/r/pull/42"
    session.close()
