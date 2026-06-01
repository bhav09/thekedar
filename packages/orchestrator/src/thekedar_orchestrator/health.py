"""Worker health and readiness HTTP server."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thekedar_orchestrator.worker import OrchestratorWorker
    from thekedar_shared.settings import Settings


async def run_health_server(worker: OrchestratorWorker, settings: Settings) -> None:
    try:
        from aiohttp import web
    except ImportError:
        return

    async def liveness(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "orchestrator-worker"})

    async def readiness(_request: web.Request) -> web.Response:
        ok, detail = await worker.check_ready()
        status = 200 if ok else 503
        return web.json_response(
            {"status": "ready" if ok else "not_ready", "detail": detail},
            status=status,
        )

    app = web.Application()
    app.router.add_get("/health", liveness)
    app.router.add_get("/ready", readiness)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8082)
    await site.start()

    while True:
        await asyncio.sleep(3600)
