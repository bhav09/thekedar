"""WhatsApp Cloud API adapter."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from thekedar_shared.schemas import Channel, MessageEvent

_MENTION_RE = re.compile(r"@(Architect|Coder|Status)", re.IGNORECASE)
_AGENT_MAP = {
    "architect": "Architect",
    "coder": "Coder",
    "status": "Status",
}


def verify_whatsapp_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.removeprefix("sha256=")
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def whatsapp_challenge_response(
    mode: str | None, token: str | None, challenge: str | None, verify_token: str
) -> str | None:
    if mode == "subscribe" and token == verify_token and challenge:
        return challenge
    return None


def parse_whatsapp_payload(payload: dict[str, Any]) -> list[MessageEvent]:
    events: list[MessageEvent] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = str(metadata.get("phone_number_id") or "unknown")
            for message in value.get("messages") or []:
                if message.get("type") != "text":
                    continue
                text_body = (message.get("text") or {}).get("body") or ""
                text = str(text_body).strip()
                if not text:
                    continue
                message_id = str(message.get("id") or "")
                user_id = str(message.get("from") or "unknown")
                thread_id = str(message.get("context", {}).get("id") or message_id)
                mentioned = _extract_mentions(text)
                events.append(
                    MessageEvent(
                        channel=Channel.WHATSAPP,
                        message_id=message_id,
                        thread_id=thread_id,
                        user_id=user_id,
                        tenant_id=phone_number_id,
                        text=text,
                        mentioned_agents=mentioned,
                        reply_token=user_id,
                        idempotency_key=f"whatsapp:{phone_number_id}:{message_id}",
                    )
                )
    return events


def _extract_mentions(text: str) -> list[str]:
    agents: list[str] = []
    for match in _MENTION_RE.finditer(text):
        token = match.group(1)
        normalized = _AGENT_MAP.get(token.lower(), token)
        if normalized not in agents:
            agents.append(normalized)
    return agents
