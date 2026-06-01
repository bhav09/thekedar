"""FastAPI app for dashboard widgets."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from thekedar_shared.db import init_db
from thekedar_shared.middleware import CorrelationIdMiddleware
from thekedar_shared.settings import get_settings

from thekedar_dashboard_hub.routes import widgets, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.session_factory = init_db(settings.database_url)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Thekedar Dashboard Hub", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(widgets.router, prefix="/api/v1")
    app.include_router(ws.router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app
