"""Approval gate API (M4) — JWT protected, tenant-scoped."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from thekedar_shared.audit import log_audit
from thekedar_shared.auth import AuthPrincipal, get_current_principal
from thekedar_shared.db import AgentRun, PendingApproval

from thekedar_dashboard_hub.deps import get_session, get_tenant

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(get_current_principal)],
)


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
        "summary": item.summary,
        "pr_url": item.pr_url,
        "status": item.status,
    }


@router.post("/{approval_id}/approve")
def approve(
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

    item.status = "approved"
    if item.run_id:
        run = session.get(AgentRun, item.run_id)
        if run:
            run.status = "completed"
    log_audit(session, item.tenant_id, principal.subject, "approval.approve", item.summary)
    session.commit()
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
    return {"id": item.id, "status": "rejected"}
