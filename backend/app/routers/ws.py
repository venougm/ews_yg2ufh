"""GET /ws/live WebSocket endpoint.

The channel is push-only: the server never expects client-sent data. The loop
only awaits `receive_text()` to detect close (via WebSocketDisconnect). Messages
pushed to clients are `{type:'reading', ...}` and `{type:'alarm', ...}` (see
app.mqtt_ingest.process_reading and app.main's offline-detection task).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import ws_manager

router = APIRouter()


@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    await ws_manager.manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.manager.disconnect(websocket)
