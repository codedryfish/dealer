"""
ws.py — WebSocket connection manager.

All state changes are broadcast to connected clients as JSON messages
with a "type" field: "state_update", "card_read", "action", "hand_result", "error".
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Any, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Send a JSON message to all connected clients."""
        message = json.dumps({"type": event_type, "data": payload})
        dead: Set[WebSocket] = set()
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
