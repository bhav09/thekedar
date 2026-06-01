"""Health and readiness probes for Cloud Run / k8s."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from thekedar_shared.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "webhook-ingress",
        "request_id": getattr(request.state, "request_id", ""),
    }


@router.get("/ready")
async def readiness(request: Request) -> dict[str, str]:
    settings = get_settings()
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
    except Exception as exc:
        return {
            "status": "not_ready",
            "service": "webhook-ingress",
            "detail": str(exc),
        }
    return {
        "status": "ready",
        "service": "webhook-ingress",
        "request_id": getattr(request.state, "request_id", ""),
    }
