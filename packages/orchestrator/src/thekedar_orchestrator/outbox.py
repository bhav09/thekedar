"""Outbound notification outbox — durable Slack/WhatsApp delivery."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from thekedar_shared.db import OutboundNotification
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


def enqueue_outbound(
    session: Session,
    settings: Settings,
    message: MessageEvent,
    text: str,
    *,
    run_id: str | None = None,
    approval_id: str | None = None,
) -> str:
    import json

    destination = message.reply_token or message.thread_id or message.user_id
    blocks = None
    if approval_id and message.channel == Channel.SLACK:
        from thekedar_orchestrator.approval_helpers import slack_approval_blocks

        blocks = slack_approval_blocks(approval_id, text)

    row = OutboundNotification(
        tenant_id=message.tenant_id,
        run_id=run_id,
        channel=message.channel.value,
        destination=destination,
        body=json.dumps(
            {"text": text, "blocks": blocks, "approval_id": approval_id},
            default=str,
        ),
        status="pending",
        approval_id=approval_id,
        next_attempt_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row.id


async def deliver_pending(
    session_factory,
    settings: Settings,
    *,
    limit: int = 20,
    registry=None,
) -> int:
    from thekedar_orchestrator.replies import deliver_outbound_row

    session = session_factory()
    sent = 0
    try:
        now = datetime.now(UTC)
        rows = (
            session.query(OutboundNotification)
            .filter(
                OutboundNotification.status.in_(("pending", "pending_retry")),
                (OutboundNotification.next_attempt_at.is_(None))
                | (OutboundNotification.next_attempt_at <= now),
            )
            .order_by(OutboundNotification.created_at.asc())
            .limit(limit)
            .all()
        )
        for row in rows:
            try:
                await deliver_outbound_row(settings, row, registry=registry)
                row.status = "sent"
                row.sent_at = datetime.now(UTC)
                row.last_error = None
                sent += 1
            except Exception as exc:
                row.retry_count += 1
                row.last_error = str(exc)[:2000]
                if row.retry_count >= settings.outbox_max_attempts:
                    row.status = "failed"
                    logger.error("Outbox permanent failure id=%s: %s", row.id, exc)
                else:
                    row.status = "pending_retry"
                    backoff = min(300, 2**row.retry_count)
                    row.next_attempt_at = now + timedelta(seconds=backoff)
            session.commit()
    finally:
        session.close()
    return sent
