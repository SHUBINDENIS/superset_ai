"""
WebSocket connection hub for session-scoped event fanout.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class SessionWebSocketHub:
    """Stores active sockets per session and broadcasts events."""

    def __init__(self) -> None:
        self._connections: Dict[str, set[WebSocket]] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop_id: Optional[int] = None

    @staticmethod
    def _current_loop_id() -> int:
        return id(asyncio.get_running_loop())

    def _get_lock(self) -> asyncio.Lock:
        loop_id = self._current_loop_id()
        if self._lock is None or self._lock_loop_id != loop_id:
            self._lock = asyncio.Lock()
            self._lock_loop_id = loop_id
        return self._lock

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._get_lock():
            self._connections.setdefault(session_id, set()).add(websocket)
        logger.debug("WS connected: session=%s", session_id)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._get_lock():
            sockets = self._connections.get(session_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(session_id, None)
        logger.debug("WS disconnected: session=%s", session_id)

    async def publish(self, session_id: str, event: Dict[str, Any]) -> int:
        payload = dict(event)
        payload.setdefault("session_id", session_id)
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        async with self._get_lock():
            sockets = list(self._connections.get(session_id, set()))

        if not sockets:
            return 0

        stale: list[WebSocket] = []
        sent = 0
        for socket in sockets:
            try:
                await socket.send_json(payload)
                sent += 1
            except Exception:
                stale.append(socket)

        if stale:
            async with self._get_lock():
                session_sockets = self._connections.get(session_id, set())
                for socket in stale:
                    session_sockets.discard(socket)
                if not session_sockets:
                    self._connections.pop(session_id, None)
        return sent


_hub: Optional[SessionWebSocketHub] = None


def get_ws_hub() -> SessionWebSocketHub:
    global _hub
    if _hub is None:
        _hub = SessionWebSocketHub()
    return _hub
