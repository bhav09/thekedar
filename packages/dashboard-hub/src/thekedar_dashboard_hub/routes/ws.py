"""WebSocket live updates (M2 basic heartbeat)."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "heartbeat", "status": "ok"})
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        return
