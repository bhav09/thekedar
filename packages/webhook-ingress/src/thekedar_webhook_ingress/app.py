"""FastAPI application factory."""

from fastapi import FastAPI
from thekedar_shared.middleware import CorrelationIdMiddleware
from thekedar_shared.settings import get_settings

from thekedar_webhook_ingress.routes import health, webhooks


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Thekedar Webhook Ingress",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url=None,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(webhooks.router)
    return app
