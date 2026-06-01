"""Webhook routes — verify, dedup, enqueue, fast ACK."""

import json
from collections.abc import Callable
from typing import Annotated, Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from thekedar_message_adapter import (
    parse_slack_event,
    parse_whatsapp_payload,
    verify_slack_signature,
    verify_whatsapp_signature,
    whatsapp_challenge_response,
)
from thekedar_shared.schemas import MessageEvent
from thekedar_shared.settings import get_settings

from thekedar_webhook_ingress.deps import get_bus, get_idempotency, get_redis

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    settings = get_settings()
    token = settings.whatsapp_verify_token or ""
    challenge = whatsapp_challenge_response(hub_mode, hub_verify_token, hub_challenge, token)
    if challenge is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    return Response(content=challenge, media_type="text/plain")


@router.post("/whatsapp")
async def whatsapp_events(
    request: Request,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    settings = get_settings()
    body = await request.body()
    _verify_or_skip(
        settings.environment,
        settings.whatsapp_app_secret,
        lambda: verify_whatsapp_signature(
            settings.whatsapp_app_secret or "", body, x_hub_signature_256
        ),
    )
    payload = json.loads(body)
    events = parse_whatsapp_payload(payload)
    await _enqueue_events(request, redis, events)
    return {"status": "accepted"}


@router.post("/slack")
async def slack_events(
    request: Request,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    x_slack_signature: Annotated[str | None, Header()] = None,
    x_slack_request_timestamp: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    settings = get_settings()
    body = await request.body()
    payload = json.loads(body)

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    _verify_or_skip(
        settings.environment,
        settings.slack_signing_secret,
        lambda: verify_slack_signature(
            settings.slack_signing_secret or "",
            body,
            x_slack_request_timestamp,
            x_slack_signature,
        ),
    )

    events = parse_slack_event(payload)
    await _enqueue_events(request, redis, events)
    return {"status": "accepted"}


def _verify_or_skip(environment: str, secret: str | None, verifier: Callable[[], bool]) -> None:
    if not secret:
        if environment == "prod":
            raise HTTPException(status_code=500, detail="Webhook secret not configured")
        return
    if not verifier():
        raise HTTPException(status_code=401, detail="Invalid signature")


async def _enqueue_events(
    request: Request, redis: aioredis.Redis, events: list[MessageEvent]
) -> None:
    if not events:
        return
    idempotency = get_idempotency(redis)
    bus = get_bus(redis)
    correlation_id = getattr(request.state, "request_id", "")

    for event in events:
        if not await idempotency.claim(event.idempotency_key):
            continue
        await bus.publish_inbound(
            {
                "correlation_id": correlation_id,
                "message": event.model_dump(mode="json"),
            }
        )
