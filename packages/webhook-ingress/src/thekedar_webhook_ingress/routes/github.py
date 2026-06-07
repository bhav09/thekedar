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

    if event_type == "push":
        # Mark context snapshot stale or trigger reindex
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")
        if repo_name:
            _mark_snapshot_stale(session, repo_name)
            import asyncio
            matching_tenant_ids = _get_matching_tenant_ids(session, repo_name)
            if matching_tenant_ids:
                asyncio.create_task(
                    _trigger_reindex_async(request.app.state.session_factory, repo_name, matching_tenant_ids)
                )

    elif event_type == "pull_request":
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
    matching_tenant_ids = _get_matching_tenant_ids(session, repo_name)
    if not matching_tenant_ids:
        return
    branch = (pr.get("head") or {}).get("ref", "")
    links = (
        session.query(TicketCodeLink)
        .filter(
            TicketCodeLink.pr_number == int(pr_number),
            TicketCodeLink.tenant_id.in_(matching_tenant_ids),
        )
        .all()
    )
    for link in links:
        link.pr_url = pr.get("html_url") or link.pr_url
        link.branch_name = branch or link.branch_name
        mergeable = pr.get("mergeable_state") or pr.get("state")
        if mergeable:
            link.ci_status = "success" if mergeable in ("clean", "merged") else str(mergeable)
    session.commit()


def _update_ci_status(session: Session, repo: dict, pr_ref: dict, conclusion: str) -> None:
    repo_name = repo.get("full_name", "")
    pr_number = pr_ref.get("number")
    if not repo_name or not pr_number:
        return
    matching_tenant_ids = _get_matching_tenant_ids(session, repo_name)
    if not matching_tenant_ids:
        return
    if conclusion == "success":
        status = "success"
    elif conclusion == "failure":
        status = "failure"
    else:
        status = "pending"
    links = (
        session.query(TicketCodeLink)
        .filter(
            TicketCodeLink.pr_number == int(pr_number),
            TicketCodeLink.tenant_id.in_(matching_tenant_ids),
        )
        .all()
    )
    for link in links:
        link.ci_status = status
    session.commit()


def _get_matching_tenant_ids(session: Session, repo_name: str) -> list[str]:
    from thekedar_shared.db import Workspace
    workspaces = session.query(Workspace).all()
    matching_tenant_ids = []
    for ws in workspaces:
        try:
            repos = json.loads(ws.github_repos or "[]")
        except Exception:
            continue
        for r in repos:
            full_repo = f"{ws.github_org}/{r}" if ws.github_org else r
            if full_repo.lower() == repo_name.lower():
                matching_tenant_ids.append(ws.tenant_id)
                break
    return matching_tenant_ids


def _mark_snapshot_stale(session: Session, repo_name: str) -> None:
    from thekedar_shared.db import ContextSnapshot
    matching_tenant_ids = _get_matching_tenant_ids(session, repo_name)
    if not matching_tenant_ids:
        return
    snapshots = (
        session.query(ContextSnapshot)
        .filter(
            ContextSnapshot.repo == repo_name,
            ContextSnapshot.tenant_id.in_(matching_tenant_ids),
        )
        .all()
    )
    # Mark stale by setting indexed_at to epoch or subtracting 48 hours to trigger reindex
    from datetime import datetime, UTC, timedelta
    stale_time = datetime.now(UTC) - timedelta(hours=48)
    for snap in snapshots:
        snap.indexed_at = stale_time
    session.commit()


async def _trigger_reindex_async(session_factory, repo_name: str, tenant_ids: list[str]) -> None:
    import asyncio
    from thekedar_context.indexer import RepoIndexer
    from thekedar_shared.workspace import WorkspaceService
    from thekedar_shared.db import Workspace
    from pathlib import Path

    def _run():
        session = session_factory()
        try:
            for tenant_id in tenant_ids:
                workspace = session.query(Workspace).filter_by(tenant_id=tenant_id).first()
                if workspace:
                    workspace_service = WorkspaceService(lambda: session)
                    primary = workspace_service.primary_repo(workspace)
                    if primary == repo_name:
                        from thekedar_orchestrator.integrations.workstation import select_remote_executor
                        from thekedar_shared.settings import get_settings
                        settings = get_settings()
                        executor = select_remote_executor(settings)
                        mount_path = executor.repo_mount_path(tenant_id, repo_name)
                        p = Path(mount_path)
                        if p.is_dir():
                            logger.info("Background indexing repo %s for tenant %s at %s", repo_name, tenant_id, p)
                            RepoIndexer().index(session, tenant_id, repo_name, p)
        except Exception as err:
            logger.error("Error in background reindex: %s", err)
        finally:
            session.close()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run)


def attach_github_routes(app) -> None:
    """Deprecated — session factory initialized in app lifespan."""
    return
