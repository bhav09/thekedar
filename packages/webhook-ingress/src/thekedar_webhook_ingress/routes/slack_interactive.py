"""Slack interactive components — approval buttons (M4/M7)."""

from __future__ import annotations

import json
import logging
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from thekedar_message_adapter import verify_slack_signature
from thekedar_shared.audit import log_audit
from thekedar_shared.db import AgentRun, PendingApproval
from thekedar_shared.resume import publish_run_resume_sync
from thekedar_shared.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks-slack-interactive"])


def get_session(request: Request) -> Session:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


@router.post("/slack/interactive")
async def slack_interactive(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    settings = get_settings()
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    require = settings.require_webhook_signature or settings.environment == "prod"

    if settings.slack_signing_secret:
        if not verify_slack_signature(
            settings.slack_signing_secret, body, timestamp, signature
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif require:
        raise HTTPException(status_code=500, detail="Slack signing secret not configured")
    else:
        logger.warning("Accepting unsigned Slack interactive payload")

    form = parse_qs(body.decode())
    payload_raw = form.get("payload", [""])[0]
    payload = json.loads(payload_raw)

    if payload.get("type") != "block_actions":
        return Response(content="", media_type="text/plain")

    action = (payload.get("actions") or [{}])[0]
    action_id = action.get("action_id", "")
    approval_id = (action.get("value") or "").strip()
    user = (payload.get("user") or {}).get("id", "slack-user")

    if not approval_id:
        return Response(content="Missing approval id", media_type="text/plain")

    item = session.get(PendingApproval, approval_id)
    if item is None:
        return Response(content="Approval not found", media_type="text/plain")

    if action_id == "approve_action":
        item.status = "approved"
        if item.run_id:
            run = session.get(AgentRun, item.run_id)
            if run and item.approval_type in ("impact_review", "plan_review", "publish_review"):
                run.status = "running"
        log_audit(session, item.tenant_id, user, "slack.approve", item.summary)
        decision = "approved"
    elif action_id == "reject_action":
        item.status = "rejected"
        if item.run_id:
            run = session.get(AgentRun, item.run_id)
            if run:
                run.status = "rejected"
        log_audit(session, item.tenant_id, user, "slack.reject", item.summary)
        decision = "rejected"
    else:
        return Response(content="Unknown action", media_type="text/plain")

    session.commit()

    if item.run_id and item.approval_type in ("impact_review", "plan_review", "publish_review"):
        try:
            publish_run_resume_sync(
                settings,
                run_id=item.run_id,
                approval_id=approval_id,
                decision=decision,
            )
        except Exception:
            logger.exception("Failed to publish resume event for run %s", item.run_id)

    return Response(
        content=json.dumps(
            {
                "response_type": "ephemeral",
                "text": f"Approval {item.status}: {item.summary}",
            }
        ),
        media_type="application/json",
    )
