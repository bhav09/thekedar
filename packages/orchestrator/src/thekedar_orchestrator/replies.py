"""Outbound replies to Slack and WhatsApp with outbox support."""

from __future__ import annotations

import json
import logging

import httpx
from thekedar_orchestrator.approval_helpers import slack_approval_blocks
from thekedar_resilience.retry import with_retry
from thekedar_shared.db import OutboundNotification
from thekedar_shared.prod_validation import allows_demo_mocks
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import IntegrationError

logger = logging.getLogger(__name__)


async def send_reply(
    settings: Settings,
    message: MessageEvent,
    text: str,
    *,
    approval_id: str | None = None,
    session=None,
    run_id: str | None = None,
) -> None:
    if session is not None:
        from thekedar_orchestrator.outbox import enqueue_outbound

        enqueue_outbound(
            session,
            settings,
            message,
            text,
            run_id=run_id,
            approval_id=approval_id,
        )
        return

    await _send_direct(settings, message, text, approval_id=approval_id)


async def deliver_outbound_row(
    settings: Settings,
    row: OutboundNotification,
    *,
    registry=None,
) -> None:
    payload = json.loads(row.body)
    text = str(payload.get("text") or "")
    blocks = payload.get("blocks")
    thread_ts = payload.get("thread_ts")
    channel = Channel(row.channel)

    if channel == Channel.SLACK:
        provider = "slack_api"
        if registry:
            await registry.check(provider)
        await _send_slack(settings, row.destination, text, blocks, thread_ts=thread_ts)
        if registry:
            await registry.record_success(provider)
    elif channel == Channel.WHATSAPP:
        provider = "whatsapp_api"
        if registry:
            await registry.check(provider)
        await _send_whatsapp(settings, row.destination, text)
        if registry:
            await registry.record_success(provider)
    else:
        raise IntegrationError(row.channel, f"Unsupported channel: {row.channel}")


async def _send_direct(
    settings: Settings,
    message: MessageEvent,
    text: str,
    *,
    approval_id: str | None = None,
) -> None:
    if message.channel == Channel.SLACK:
        blocks = slack_approval_blocks(approval_id, text) if approval_id else None
        await _send_slack(
            settings,
            message.reply_token or message.thread_id,
            text,
            blocks,
            thread_ts=message.thread_id,
        )
    elif message.channel == Channel.WHATSAPP:
        await _send_whatsapp(settings, message.reply_token or message.user_id, text)


async def _send_slack(
    settings: Settings,
    channel_id: str,
    text: str,
    blocks: list[dict] | None = None,
    thread_ts: str | None = None,
) -> None:
    token = settings.slack_bot_token.get_secret_value() if settings.slack_bot_token else None
    if not token:
        if allows_demo_mocks(settings):
            logger.info(
                "Slack reply (no token): channel=%s thread=%s text=%s",
                channel_id,
                thread_ts or "none",
                text[:120],
            )
            return
        raise IntegrationError("slack", "SLACK_BOT_TOKEN not configured")

    payload: dict = {"channel": channel_id, "text": text[:3000]}
    if blocks:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts

    @with_retry(settings.provider_retry_max)
    async def _post() -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            if not body.get("ok"):
                raise RuntimeError(f"Slack API error: {body.get('error')}")

    await _post()


async def _send_whatsapp(settings: Settings, to_user: str, text: str) -> None:
    token = (
        settings.whatsapp_access_token.get_secret_value()
        if settings.whatsapp_access_token
        else None
    )
    phone_id = settings.whatsapp_phone_number_id
    if not token or not phone_id:
        if allows_demo_mocks(settings):
            logger.info("WhatsApp reply (no token): to=%s text=%s", to_user, text[:120])
            return
        raise IntegrationError("whatsapp", "WhatsApp credentials not configured")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"

    @with_retry(settings.provider_retry_max)
    async def _post() -> None:
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

    await _post()
