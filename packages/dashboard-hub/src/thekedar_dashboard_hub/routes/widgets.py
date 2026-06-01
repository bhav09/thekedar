"""Widget read-model API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from thekedar_shared.db import AgentRun, PendingApproval, WorkstationHealth

router = APIRouter(prefix="/widgets", tags=["widgets"])


def get_session(request: Request) -> Session:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


@router.get("/active-runs")
def active_runs(session: Annotated[Session, Depends(get_session)]) -> dict:
    runs = (
        session.query(AgentRun)
        .filter(AgentRun.status.in_(["running", "awaiting_approval"]))
        .order_by(AgentRun.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "widget": "active-runs",
        "items": [
            {
                "run_id": r.id,
                "channel": r.channel,
                "user_id": r.user_id,
                "workflow": r.workflow,
                "status": r.status,
                "current_node": r.current_node,
                "trigger_text": r.trigger_text[:200],
            }
            for r in runs
        ],
    }


@router.get("/pending-approvals")
def pending_approvals(session: Annotated[Session, Depends(get_session)]) -> dict:
    items = (
        session.query(PendingApproval)
        .filter(PendingApproval.status == "pending")
        .order_by(PendingApproval.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "widget": "pending-approvals",
        "items": [
            {
                "id": a.id,
                "approval_type": a.approval_type,
                "summary": a.summary,
                "status": a.status,
            }
            for a in items
        ],
    }


@router.get("/workstation-health")
def workstation_health(session: Annotated[Session, Depends(get_session)]) -> dict:
    rows = session.query(WorkstationHealth).order_by(WorkstationHealth.tenant_id).all()
    return {
        "widget": "workstation-health",
        "items": [
            {
                "tenant_id": w.tenant_id,
                "name": w.name,
                "state": w.state,
                "region": w.region,
            }
            for w in rows
        ],
    }
