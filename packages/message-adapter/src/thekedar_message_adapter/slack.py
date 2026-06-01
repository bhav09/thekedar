"""Slack Events API adapter."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Any

from thekedar_shared.schemas import Channel, MessageEvent

_MENTION_RE = re.compile(r"<@(U[A-Z0-9]+)>|@(Architect|Coder|Status)", re.IGNORECASE)
_AGENT_MAP = {
    "architect": "Architect",
    "coder": "Coder",
    "status": "Status",
}


def verify_slack_signature(
    signing_secret: str,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    *,
    max_age_seconds: int = 300,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > max_age_seconds:
            return False
    except ValueError:
        return False

    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def parse_slack_event(
    payload: dict[str, Any], *, default_tenant_id: str = "default"
) -> list[MessageEvent]:
    """Parse Slack event_callback payloads into canonical messages."""
    if payload.get("type") == "url_verification":
        return []

    event = payload.get("event") or {}
    if event.get("type") != "message":
        return []
    if event.get("subtype") in {"bot_message", "message_changed", "message_deleted"}:
        return []
    if event.get("bot_id"):
        return []

    text = str(event.get("text") or "").strip()
    if not text:
        return []

    user_id = str(event.get("user") or "unknown")
    channel_id = str(event.get("channel") or payload.get("channel") or "unknown")
    team_id = str(payload.get("team_id") or default_tenant_id)
    message_id = str(
        event.get("client_msg_id") or event.get("ts") or f"{channel_id}:{event.get('ts')}"
    )
    thread_id = str(event.get("thread_ts") or event.get("ts") or message_id)

    mentioned = _extract_mentions(text)

    return [
        MessageEvent(
            channel=Channel.SLACK,
            message_id=message_id,
            thread_id=thread_id,
            user_id=user_id,
            tenant_id=team_id,
            text=text,
            mentioned_agents=mentioned,
            reply_token=channel_id,
            idempotency_key=f"slack:{team_id}:{message_id}",
        )
    ]


def _extract_mentions(text: str) -> list[str]:
    agents: list[str] = []
    for match in _MENTION_RE.finditer(text):
        token = match.group(1) or match.group(2)
        if token and token.startswith("U"):
            continue
        normalized = _AGENT_MAP.get((token or "").lower(), token or "")
        if normalized and normalized not in agents:
            agents.append(normalized)
    return agents
