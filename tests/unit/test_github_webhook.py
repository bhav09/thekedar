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
    from thekedar_shared.db import Workspace
    session.add(
        Workspace(
            tenant_id="default",
            name="Default Workspace",
            github_org="o",
            github_repos=json.dumps(["r"]),
        )
    )
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


def test_github_webhook_scoped_by_tenant_and_repo(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()

    session = client.app.state.session_factory()
    from thekedar_shared.db import Workspace
    session.add(
        Workspace(
            tenant_id="tenant-a",
            name="Tenant A Workspace",
            github_org="org-a",
            github_repos=json.dumps(["repo-a"]),
        )
    )
    session.add(
        Workspace(
            tenant_id="tenant-b",
            name="Tenant B Workspace",
            github_org="org-b",
            github_repos=json.dumps(["repo-b"]),
        )
    )
    session.add(
        TicketCodeLink(tenant_id="tenant-a", issue_key="THE-A", pr_number=42, ci_status="pending")
    )
    session.add(
        TicketCodeLink(tenant_id="tenant-b", issue_key="THE-B", pr_number=42, ci_status="pending")
    )
    session.commit()
    session.close()

    body = json.dumps(
        {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "html_url": "https://github.com/org-a/repo-a/pull/42",
                "head": {"ref": "b"},
            },
            "repository": {"full_name": "org-a/repo-a"},
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
    link_a = session.query(TicketCodeLink).filter_by(tenant_id="tenant-a", issue_key="THE-A").first()
    link_b = session.query(TicketCodeLink).filter_by(tenant_id="tenant-b", issue_key="THE-B").first()
    assert link_a is not None
    assert link_b is not None
    assert link_a.pr_url == "https://github.com/org-a/repo-a/pull/42"
    assert link_b.pr_url is None  # Remains untouched!
    session.close()


def test_github_push_webhook_marks_snapshot_stale(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()

    session = client.app.state.session_factory()
    from thekedar_shared.db import Workspace, ContextSnapshot
    session.add(
        Workspace(
            tenant_id="tenant-a",
            name="Tenant A Workspace",
            github_org="org-a",
            github_repos=json.dumps(["repo-a"]),
        )
    )
    from datetime import datetime, UTC
    now = datetime.now(UTC)
    session.add(
        ContextSnapshot(
            id="snap-1",
            tenant_id="tenant-a",
            repo="org-a/repo-a",
            sha="some-sha",
            branch="main",
            indexed_at=now,
        )
    )
    session.commit()
    session.close()

    body = json.dumps(
        {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org-a/repo-a"},
        }
    ).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
    )
    assert resp.status_code == 200

    session = client.app.state.session_factory()
    snap = session.query(ContextSnapshot).filter_by(id="snap-1").first()
    assert snap is not None
    assert (now - snap.indexed_at.replace(tzinfo=UTC)).total_seconds() > 3600 * 24  # Marked stale (>24h age)
    session.close()
