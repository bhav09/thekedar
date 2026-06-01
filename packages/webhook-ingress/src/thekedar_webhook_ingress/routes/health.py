"""Health and readiness probes for Cloud Run / k8s."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness(request: Request) -> dict[str, str]:
    """Liveness — process is up."""
    return {
        "status": "ok",
        "service": "webhook-ingress",
        "request_id": getattr(request.state, "request_id", ""),
    }


@router.get("/ready")
async def readiness(request: Request) -> dict[str, str]:
    """Readiness — dependencies available (extended in M2 with Redis/Postgres checks)."""
    return {
        "status": "ready",
        "service": "webhook-ingress",
        "request_id": getattr(request.state, "request_id", ""),
    }
