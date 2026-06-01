"""Canonical event schemas — used by message-adapter and orchestrator (M2+)."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    SLACK = "slack"


class MessageEvent(BaseModel):
    """Normalized inbound message from any channel."""

    channel: Channel
    message_id: str
    thread_id: str
    user_id: str
    tenant_id: str
    text: str
    mentioned_agents: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    reply_token: str | None = None
    idempotency_key: str
