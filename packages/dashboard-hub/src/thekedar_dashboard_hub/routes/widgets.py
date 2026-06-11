"""Widget read-model API — tenant-scoped, JWT protected."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from thekedar_shared.auth import get_current_principal
from thekedar_shared.db import (
    AgentRun,
    AuditLog,
    CostRecord,
    MessagingActivity,
    PendingApproval,
    TicketCodeLink,
    WorkstationHealth,
    Workspace,
)
from pydantic import BaseModel
from fastapi import HTTPException

from thekedar_dashboard_hub.deps import get_session, get_tenant

router = APIRouter(
    prefix="/widgets",
    tags=["widgets"],
    dependencies=[Depends(get_current_principal)],
)


@router.get("/active-runs")
def active_runs(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    runs = (
        session.query(AgentRun)
        .filter_by(tenant_id=tenant_id)
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
def pending_approvals(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    items = (
        session.query(PendingApproval)
        .filter_by(tenant_id=tenant_id, status="pending")
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
def workstation_health(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = session.query(WorkstationHealth).filter_by(tenant_id=tenant_id).all()
    return {
        "widget": "workstation-health",
        "items": [
            {
                "tenant_id": w.tenant_id,
                "name": w.name,
                "state": w.state,
                "region": w.region,
                "commits_behind_main": w.commits_behind_main,
                "last_activity_at": w.last_activity_at.isoformat() if w.last_activity_at else None,
            }
            for w in rows
        ],
    }


@router.get("/ticket-code")
def ticket_code_links(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(TicketCodeLink)
        .filter_by(tenant_id=tenant_id)
        .order_by(TicketCodeLink.updated_at.desc())
        .limit(30)
        .all()
    )
    return {
        "widget": "ticket-code",
        "items": [
            {
                "issue_key": r.issue_key,
                "issue_summary": r.issue_summary,
                "issue_status": r.issue_status,
                "branch_name": r.branch_name,
                "pr_url": r.pr_url,
                "pr_number": r.pr_number,
                "ci_status": r.ci_status,
            }
            for r in rows
        ],
    }


@router.get("/pr-pipeline")
def pr_pipeline(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(TicketCodeLink)
        .filter_by(tenant_id=tenant_id)
        .filter(TicketCodeLink.pr_url.isnot(None))
        .order_by(TicketCodeLink.updated_at.desc())
        .limit(20)
        .all()
    )
    return {
        "widget": "pr-pipeline",
        "items": [
            {
                "issue_key": r.issue_key,
                "pr_url": r.pr_url,
                "ci_status": r.ci_status,
                "branch_name": r.branch_name,
            }
            for r in rows
        ],
    }


@router.get("/cost-summary")
def cost_summary(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(CostRecord)
        .filter_by(tenant_id=tenant_id)
        .order_by(CostRecord.created_at.desc())
        .limit(200)
        .all()
    )
    totals: dict[str, float] = {}
    for row in rows:
        totals[row.category] = totals.get(row.category, 0.0) + row.amount_usd
    return {
        "widget": "cost-summary",
        "totals_usd": totals,
        "recent": [
            {
                "category": r.category,
                "amount_usd": r.amount_usd,
                "run_id": r.run_id,
            }
            for r in rows[:10]
        ],
    }


@router.get("/audit-trail")
def audit_trail(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(AuditLog)
        .filter_by(tenant_id=tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "widget": "audit-trail",
        "items": [
            {
                "actor": r.actor,
                "action": r.action,
                "detail": r.detail,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/messaging-activity")
def messaging_activity(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(MessagingActivity)
        .filter_by(tenant_id=tenant_id)
        .order_by(MessagingActivity.created_at.desc())
        .limit(30)
        .all()
    )
    return {
        "widget": "messaging-activity",
        "items": [
            {
                "channel": r.channel,
                "direction": r.direction,
                "text": r.text[:200],
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/slack-app-home")
def slack_app_home(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    runs = (
        session.query(AgentRun)
        .filter_by(tenant_id=tenant_id)
        .order_by(AgentRun.created_at.desc())
        .limit(5)
        .all()
    )
    approvals = (
        session.query(PendingApproval)
        .filter_by(tenant_id=tenant_id, status="pending")
        .limit(5)
        .all()
    )
    run_lines = "\n".join(f"• {r.workflow} [{r.status}]" for r in runs) or "No recent runs"
    approval_lines = "\n".join(f"• {a.summary}" for a in approvals) or "No pending approvals"
    return {
        "widget": "slack-app-home",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "Thekedar"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Recent runs*\n{run_lines}"}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Pending approvals*\n{approval_lines}"},
            },
        ],
    }


@router.get("/nl-query")
def nl_query(
    q: str,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    needle = q.strip().lower()
    if not needle:
        return {"widget": "nl-query", "query": q, "results": []}

    runs = (
        session.query(AgentRun)
        .filter_by(tenant_id=tenant_id)
        .order_by(AgentRun.created_at.desc())
        .limit(100)
        .all()
    )
    audits = (
        session.query(AuditLog)
        .filter_by(tenant_id=tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
        .all()
    )
    results: list[dict] = []

    for run in runs:
        hay = f"{run.workflow} {run.trigger_text} {run.status}".lower()
        if needle in hay:
            results.append({"type": "run", "id": run.id, "summary": run.trigger_text[:120]})

    for entry in audits:
        hay = f"{entry.action} {entry.detail}".lower()
        if needle in hay:
            results.append({"type": "audit", "action": entry.action, "detail": entry.detail[:120]})

    return {"widget": "nl-query", "query": q, "results": results[:20]}


@router.get("/looker-export")
def looker_export(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = (
        session.query(CostRecord)
        .filter_by(tenant_id=tenant_id)
        .order_by(CostRecord.created_at.desc())
        .limit(500)
        .all()
    )
    csv_lines = ["tenant_id,category,amount_usd,run_id,created_at"]
    for r in rows:
        csv_lines.append(
            f"{r.tenant_id},{r.category},{r.amount_usd},{r.run_id or ''},{r.created_at.isoformat()}"
        )
    return {
        "widget": "looker-export",
        "format": "csv",
        "rows": len(rows),
        "csv": "\n".join(csv_lines),
    }


class SettingsUpdateRequest(BaseModel):
    github_project_url: str | None = None
    jira_project_key: str | None = None
    slack_team_id: str | None = None
    whatsapp_phone_number_id: str | None = None


@router.get("/workspaces")
def workspaces_list(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    workspaces = session.query(Workspace).order_by(Workspace.name.asc()).all()
    return {
        "widget": "workspaces",
        "items": [
            {
                "tenant_id": w.tenant_id,
                "name": w.name,
                "jira_project_key": w.jira_project_key,
                "github_project_url": w.github_project_url,
                "slack_team_id": w.slack_team_id,
                "whatsapp_phone_number_id": w.whatsapp_phone_number_id,
            }
            for w in workspaces
        ]
    }


@router.post("/workspaces/settings")
def update_settings(
    body: SettingsUpdateRequest,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    workspace = session.query(Workspace).filter_by(tenant_id=tenant_id).first()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if body.github_project_url is not None:
        workspace.github_project_url = body.github_project_url
        from thekedar_shared.workspace import parse_github_url
        import json
        parsed = parse_github_url(body.github_project_url)
        if parsed:
            workspace.github_org = parsed[0]
            workspace.github_repos = json.dumps(parsed[1])
            
    if body.jira_project_key is not None:
        workspace.jira_project_key = body.jira_project_key
        
    if body.slack_team_id is not None:
        workspace.slack_team_id = body.slack_team_id
        
    if body.whatsapp_phone_number_id is not None:
        workspace.whatsapp_phone_number_id = body.whatsapp_phone_number_id
        
    session.commit()
    return {
        "status": "success",
        "workspace": {
            "tenant_id": workspace.tenant_id,
            "name": workspace.name,
            "github_project_url": workspace.github_project_url,
            "jira_project_key": workspace.jira_project_key,
            "slack_team_id": workspace.slack_team_id,
            "whatsapp_phone_number_id": workspace.whatsapp_phone_number_id,
        }
    }
