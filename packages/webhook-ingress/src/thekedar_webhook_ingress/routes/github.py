"""GitHub webhook — PR/CI status updates (M4)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from thekedar_shared.db import TicketCodeLink
from thekedar_shared.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks-github"])


def get_session(request: Request) -> Session:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _verify_github_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/github")
async def github_events(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    settings = get_settings()
    body = await request.body()
    secret = (
        settings.github_webhook_secret.get_secret_value()
        if settings.github_webhook_secret
        else ""
    )
    require = settings.require_webhook_signature or settings.environment == "prod"

    if secret:
        if not _verify_github_signature(body, x_hub_signature_256, secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif require:
        raise HTTPException(status_code=500, detail="GitHub webhook secret not configured")
    else:
        logger.warning("Accepting unsigned GitHub webhook")

    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type == "pull_request":
        action = payload.get("action")
        pr = payload.get("pull_request") or {}
        if action in ("opened", "synchronize", "closed"):
            _update_pr_link(session, payload.get("repository", {}), pr)

    elif event_type == "check_run":
        check = payload.get("check_run") or {}
        conclusion = check.get("conclusion") or "pending"
        prs = (check.get("pull_requests") or []) if check else []
        for pr_ref in prs:
            _update_ci_status(session, payload.get("repository", {}), pr_ref, conclusion)

    return {"status": "accepted"}


def _update_pr_link(session: Session, repo: dict, pr: dict) -> None:
    repo_name = repo.get("full_name", "")
    pr_number = pr.get("number")
    if not repo_name or not pr_number:
        return
    branch = (pr.get("head") or {}).get("ref", "")
    links = session.query(TicketCodeLink).filter_by(pr_number=int(pr_number)).all()
    for link in links:
        link.pr_url = pr.get("html_url") or link.pr_url
        link.branch_name = branch or link.branch_name
        mergeable = pr.get("mergeable_state") or pr.get("state")
        if mergeable:
            link.ci_status = "success" if mergeable in ("clean", "merged") else str(mergeable)
    session.commit()


def _update_ci_status(session: Session, repo: dict, pr_ref: dict, conclusion: str) -> None:
    pr_number = pr_ref.get("number")
    if not pr_number:
        return
    if conclusion == "success":
        status = "success"
    elif conclusion == "failure":
        status = "failure"
    else:
        status = "pending"
    links = session.query(TicketCodeLink).filter_by(pr_number=int(pr_number)).all()
    for link in links:
        link.ci_status = status
    session.commit()


def attach_github_routes(app) -> None:
    """Deprecated — session factory initialized in app lifespan."""
    return
