"""Audit, cost, and activity helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from thekedar_shared.db import AuditLog, CostRecord, MessagingActivity


def log_audit(session: Session, tenant_id: str, actor: str, action: str, detail: str = "") -> None:
    session.add(
        AuditLog(tenant_id=tenant_id, actor=actor, action=action, detail=detail[:2000])
    )


def log_cost(
    session: Session,
    tenant_id: str,
    category: str,
    amount_usd: float,
    run_id: str | None = None,
) -> None:
    session.add(
        CostRecord(
            tenant_id=tenant_id,
            category=category,
            amount_usd=amount_usd,
            run_id=run_id,
        )
    )


def log_message(
    session: Session,
    tenant_id: str,
    channel: str,
    direction: str,
    text: str,
) -> None:
    session.add(
        MessagingActivity(
            tenant_id=tenant_id,
            channel=channel,
            direction=direction,
            text=text[:2000],
        )
    )
