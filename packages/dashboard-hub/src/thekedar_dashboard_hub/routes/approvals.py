"""Approval gate API (M4/M7) — JWT protected, tenant-scoped."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from thekedar_shared.audit import log_audit
from thekedar_shared.auth import AuthPrincipal, get_current_principal
from thekedar_shared.db import AgentRun, PendingApproval
from thekedar_shared.resume import publish_run_resume_sync
from thekedar_shared.settings import get_settings

from thekedar_dashboard_hub.deps import get_session, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(get_current_principal)],
)


class ApprovalDecision(BaseModel):
    user_message: str | None = None


@router.get("/{approval_id}")
def get_approval(
    approval_id: str,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = session.get(PendingApproval, approval_id)
    if item is None or item.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "run_id": item.run_id,
        "approval_type": item.approval_type,
        "stage": item.stage,
        "summary": item.summary,
        "payload_json": item.payload_json,
        "pr_url": item.pr_url,
        "status": item.status,
    }


def _resume_if_coder_pipeline(item: PendingApproval, decision: str, user_message: str | None) -> None:
    if not item.run_id:
        return
    if item.approval_type not in ("impact_review", "plan_review", "publish_review"):
        return
    settings = get_settings()
    publish_run_resume_sync(
        settings,
        run_id=item.run_id,
        approval_id=item.id,
        decision=decision,
        user_message=user_message,
    )


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    tenant_id: Annotated[str, Depends(get_tenant)],
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    session: Annotated[Session, Depends(get_session)],
    body: ApprovalDecision | None = None,
) -> dict:
    item = session.get(PendingApproval, approval_id)
    if item is None or item.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {item.status}")

    item.status = "approved"
    if item.run_id:
        run = session.get(AgentRun, item.run_id)
        if run:
            if item.approval_type in ("impact_review", "plan_review", "publish_review"):
                run.status = "running"
            else:
                run.status = "completed"
    log_audit(session, item.tenant_id, principal.subject, "approval.approve", item.summary)
    session.commit()

    user_message = body.user_message if body else None
    try:
        _resume_if_coder_pipeline(item, "approved", user_message)
    except Exception:
        logger.exception("Failed to resume run after dashboard approval %s", item.id)

    return {"id": item.id, "status": "approved"}


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    tenant_id: Annotated[str, Depends(get_tenant)],
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = session.get(PendingApproval, approval_id)
    if item is None or item.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {item.status}")

    item.status = "rejected"
    if item.run_id:
        run = session.get(AgentRun, item.run_id)
        if run:
            run.status = "rejected"
    log_audit(session, item.tenant_id, principal.subject, "approval.reject", item.summary)
    session.commit()

    try:
        _resume_if_coder_pipeline(item, "rejected", None)
    except Exception:
        logger.exception("Failed to resume run after dashboard rejection %s", item.id)

    return {"id": item.id, "status": "rejected"}
