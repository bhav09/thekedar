"""Webhook routes — stubs for M2 implementation."""

from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def whatsapp_verify() -> dict[str, str]:
    """Meta webhook verification — implemented in M2."""
    return {"status": "not_implemented", "milestone": "M2"}


@router.post("/whatsapp")
async def whatsapp_events() -> dict[str, str]:
    """WhatsApp inbound events — implemented in M2."""
    return {"status": "accepted", "note": "M0 stub — async pipeline in M2"}


@router.post("/slack")
async def slack_events() -> dict[str, str]:
    """Slack Events API — implemented in M2."""
    return {"status": "accepted", "note": "M0 stub — async pipeline in M2"}
