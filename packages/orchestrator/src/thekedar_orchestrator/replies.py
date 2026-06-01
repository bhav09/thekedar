"""Outbound replies to Slack and WhatsApp."""

from __future__ import annotations

import logging

import httpx
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


async def send_reply(settings: Settings, message: MessageEvent, text: str) -> None:
    if message.channel == Channel.SLACK:
        await _send_slack(settings, message.reply_token or "", text)
    elif message.channel == Channel.WHATSAPP:
        await _send_whatsapp(settings, message.reply_token or "", text)


async def _send_slack(settings: Settings, channel_id: str, text: str) -> None:
    token = settings.slack_bot_token.get_secret_value() if settings.slack_bot_token else None
    if not token:
        logger.info("Slack reply (no token): channel=%s text=%s", channel_id, text[:120])
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel_id, "text": text},
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Slack API error: {body.get('error')}")


async def _send_whatsapp(settings: Settings, to_user: str, text: str) -> None:
    token = (
        settings.whatsapp_access_token.get_secret_value()
        if settings.whatsapp_access_token
        else None
    )
    phone_id = settings.whatsapp_phone_number_id
    if not token or not phone_id:
        logger.info("WhatsApp reply (no token): to=%s text=%s", to_user, text[:120])
        return
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_user,
                "type": "text",
                "text": {"body": text[:4096]},
            },
        )
        response.raise_for_status()
