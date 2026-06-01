"""Domain events emitted across Thekedar services."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    INBOUND_MESSAGE = "inbound.message"
    AGENT_RUN_STARTED = "agent.run.started"
    AGENT_RUN_COMPLETED = "agent.run.completed"
    AGENT_RUN_FAILED = "agent.run.failed"
    APPROVAL_REQUESTED = "approval.requested"
    WORKSTATION_STATE_CHANGED = "workstation.state_changed"


class DomainEvent(BaseModel):
    type: EventType
    tenant_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
