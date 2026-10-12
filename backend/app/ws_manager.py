"""WebSocket connection manager / broadcaster.

Everything touching the connection set -- connect, disconnect, and broadcast via
`run_coroutine_threadsafe` -- ends up running on the one event-loop thread, so
`asyncio.Lock` is the correct primitive here (not `threading.Lock`).

`broadcast_json` takes a snapshot list of the connection set while holding the
lock briefly, released before any `send_json` calls so a slow client can't block
the lock for others. It then iterates the snapshot and wraps each `send_json` in
its own try/except so one dead/half-closed socket can never abort delivery to the
remaining connections.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            snapshot = list(self._connections)

        dead: list[WebSocket] = []
        for ws in snapshot:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.warning("broadcast send failed, dropping connection: error=%s", e)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    def broadcast_json_threadsafe(self, payload: dict[str, Any], loop: asyncio.AbstractEventLoop) -> None:
        """For use from the MQTT thread: schedules `broadcast_json` onto the
        FastAPI event loop captured at startup."""
        asyncio.run_coroutine_threadsafe(self.broadcast_json(payload), loop)


# Module-level singleton shared by routers/ws.py (connect/disconnect) and
# mqtt_ingest.py (broadcast_json_threadsafe from the MQTT thread).
manager = ConnectionManager()
