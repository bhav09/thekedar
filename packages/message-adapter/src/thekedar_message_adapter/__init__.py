"""WhatsApp and Slack → canonical MessageEvent adapters."""

from thekedar_message_adapter.slack import parse_slack_event, verify_slack_signature
from thekedar_message_adapter.whatsapp import (
    parse_whatsapp_payload,
    verify_whatsapp_signature,
    whatsapp_challenge_response,
)

__all__ = [
    "parse_slack_event",
    "parse_whatsapp_payload",
    "verify_slack_signature",
    "verify_whatsapp_signature",
    "whatsapp_challenge_response",
]
