"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from thekedar_shared.db import init_db
from thekedar_shared.middleware import CorrelationIdMiddleware
from thekedar_shared.settings import get_settings
from thekedar_shared.settings_validation import validate_settings

from thekedar_webhook_ingress.middleware import MaxBodySizeMiddleware
from thekedar_webhook_ingress.routes import github, health, slack_interactive, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    validate_settings(settings)
    app.state.settings = settings
    app.state.session_factory = init_db(settings.database_url)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Thekedar Webhook Ingress",
        version="0.4.0",
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(webhooks.router)
    app.include_router(github.router)
    app.include_router(slack_interactive.router)
    return app
