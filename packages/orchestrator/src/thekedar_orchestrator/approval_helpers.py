"""Approval helpers for multi-stage coder pipeline."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session
from thekedar_shared.db import PendingApproval


def create_approval(
    session: Session,
    *,
    tenant_id: str,
    run_id: str,
    approval_type: str,
    stage: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    channel_reply_token: str | None = None,
    pr_url: str | None = None,
) -> PendingApproval:
    approval = PendingApproval(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        run_id=run_id,
        approval_type=approval_type,
        stage=stage,
        summary=summary,
        payload_json=json.dumps(payload) if payload else None,
        channel_reply_token=channel_reply_token,
        pr_url=pr_url,
        status="pending",
    )
    session.add(approval)
    return approval


def slack_approval_blocks(approval_id: str, summary: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:2800]},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "approve_action",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": "reject_action",
                    "value": approval_id,
                },
            ],
        },
    ]
