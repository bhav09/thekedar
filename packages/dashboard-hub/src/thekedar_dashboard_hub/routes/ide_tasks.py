"""IDE Tasks API router (Phase D) — JWT protected, tenant-scoped bidirectional queue."""

from __future__ import annotations

import logging
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from thekedar_shared.auth import get_current_principal
from thekedar_shared.db import IdeTask

from thekedar_dashboard_hub.deps import get_session, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ide-tasks",
    tags=["ide-tasks"],
    dependencies=[Depends(get_current_principal)],
)


class CreateIdeTask(BaseModel):
    run_id: str
    payload_json: str


class ClaimRequest(BaseModel):
    claimed_by: str


class CompleteRequest(BaseModel):
    result_json: str


class FailRequest(BaseModel):
    error: str


@router.post("", response_model=dict)
def create_task(
    body: CreateIdeTask,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    task = IdeTask(
        tenant_id=tenant_id,
        run_id=body.run_id,
        status="pending",
        payload_json=body.payload_json,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    # D2. WebSocket push trigger
    try:
        from thekedar_dashboard_hub.routes.ws import broadcast_to_tenant
        # We broadcast the task creation event to any connected WebSocket clients of this tenant
        asyncio_avail = True
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_to_tenant(tenant_id, {
                "type": "ide_task",
                "task_id": task.id,
                "run_id": task.run_id,
            }))
        except RuntimeError:
            pass  # Not running in async loop (e.g. sync wsGI/ASGI thread)
    except Exception as e:
        logger.warning("WebSocket broadcast failed during task creation: %s", e)

    return {"status": "created", "id": task.id}


@router.get("/pending", response_model=list[dict])
def get_pending_tasks(
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict]:
    tasks = session.query(IdeTask).filter_by(tenant_id=tenant_id, status="pending").all()
    return [
        {
            "id": t.id,
            "tenant_id": t.tenant_id,
            "run_id": t.run_id,
            "status": t.status,
            "payload_json": t.payload_json,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("/{id}/claim", response_model=dict)
def claim_task(
    id: str,
    body: ClaimRequest,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    task = session.get(IdeTask, id)
    if task is None or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("pending", "claimed"):
        raise HTTPException(status_code=400, detail=f"Task is in status {task.status}")

    task.status = "claimed"
    task.claimed_by = body.claimed_by
    task.claimed_at = datetime.now(UTC)
    session.commit()
    return {"status": "claimed", "id": task.id}


@router.post("/{id}/complete", response_model=dict)
def complete_task(
    id: str,
    body: CompleteRequest,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    task = session.get(IdeTask, id)
    if task is None or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    task.result_json = body.result_json
    task.completed_at = datetime.now(UTC)
    session.commit()
    return {"status": "completed", "id": task.id}


@router.post("/{id}/fail", response_model=dict)
def fail_task(
    id: str,
    body: FailRequest,
    tenant_id: Annotated[str, Depends(get_tenant)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    task = session.get(IdeTask, id)
    if task is None or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "failed"
    task.result_json = json.dumps({"success": False, "summary": "Task failed", "error": body.error})
    task.completed_at = datetime.now(UTC)
    session.commit()
    return {"status": "failed", "id": task.id}
