"""WebSocket live updates (M2 basic heartbeat)."""

from __future__ import annotations

import asyncio
import collections
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

logger = logging.getLogger(__name__)

# Maps tenant_id -> Set of active WebSocket connections
_active_connections: Dict[str, Set[WebSocket]] = collections.defaultdict(set)


async def broadcast_to_tenant(tenant_id: str, message: dict) -> None:
    """Broadcast an event to all connected WebSocket clients for a specific tenant."""
    sockets = _active_connections.get(tenant_id)
    if not sockets:
        return

    logger.info("Broadcasting WebSocket message to tenant %s: %s", tenant_id, message)
    dead_sockets = set()
    for ws in list(sockets):
        try:
            await ws.send_json(message)
        except Exception as e:
            logger.debug("Failed to send WebSocket message to connection: %s", e)
            dead_sockets.add(ws)

    for ws in dead_sockets:
        sockets.discard(ws)


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    # WebSocket auth on join
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return
    from thekedar_shared.settings import get_settings
    from thekedar_shared.auth import decode_access_token
    try:
        principal = decode_access_token(get_settings(), token)
    except Exception:
        await websocket.close(code=4002, reason="Invalid authentication token")
        return

    await websocket.accept()
    tenant_id = principal.tenant_id
    _active_connections[tenant_id].add(websocket)

    try:
        while True:
            await websocket.send_json({"type": "heartbeat", "status": "ok", "tenant_id": tenant_id})
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        return
    finally:
        _active_connections[tenant_id].discard(websocket)
