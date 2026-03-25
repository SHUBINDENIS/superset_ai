"""
WebSocket API for real-time chat updates.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

from .ai_agent import get_session_manager
from .auth_service import get_auth_service
from .ws_events import get_ws_hub

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="Superset AI Assistant WebSocket API",
    version="1.0.0",
)


def _normalize_messages(payload_messages: Any, user_message: str) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    if isinstance(payload_messages, list):
        for item in payload_messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                normalized.append({"role": role, "content": content})

    clean_user_message = str(user_message).strip()
    if not clean_user_message:
        return normalized
    if not normalized or normalized[-1].get("role") != "user":
        normalized.append({"role": "user", "content": clean_user_message})
    elif normalized[-1].get("content") != clean_user_message:
        normalized[-1]["content"] = clean_user_message
    return normalized


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.websocket("/ws/chat/{session_id}")
async def chat_ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    manager = get_session_manager()
    auth_service = get_auth_service()
    hub = get_ws_hub()
    clean_session_id = str(session_id).strip()
    if not clean_session_id:
        await websocket.close(code=1008, reason="Invalid session_id")
        return

    await hub.connect(clean_session_id, websocket)
    await hub.publish(
        clean_session_id,
        {
            "type": "connected",
            "message": "WebSocket connection established.",
        },
    )
    try:
        while True:
            payload = await websocket.receive_json()
            event_type = str(payload.get("type", "chat")).strip().lower()

            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if event_type != "chat":
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "validation",
                        "message": f"Unsupported payload type: {event_type}",
                    }
                )
                continue

            user_message = str(payload.get("message", "")).strip()
            if not user_message:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "validation",
                        "message": "Message cannot be empty.",
                    }
                )
                continue

            messages = _normalize_messages(payload.get("messages"), user_message)
            if not messages:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "validation",
                        "message": "Message history payload is invalid.",
                    }
                )
                continue

            auth_token = str(payload.get("auth_token", "")).strip()
            if not auth_token:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "auth",
                        "message": "auth_token is required.",
                    }
                )
                continue

            try:
                token_context = auth_service.validate_token(auth_token)
                username = str(token_context.get("username", "")).strip()
                if not username:
                    raise ValueError("Token subject is missing.")
                expected_session_id = str(token_context.get("session_id", "")).strip()
                if expected_session_id and expected_session_id != clean_session_id:
                    raise ValueError("Session ID mismatch for authenticated user.")
            except ValueError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "auth",
                        "message": str(exc),
                    }
                )
                continue

            try:
                agent = await manager.get_or_create_agent(
                    clean_session_id,
                    owner=username,
                )
            except PermissionError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "stage": "auth",
                        "message": "Session does not belong to authenticated user.",
                    }
                )
                continue

            async def emit(event: Dict[str, Any]) -> None:
                await hub.publish(clean_session_id, event)

            await agent.chat_stream(messages=messages, event_callback=emit)
    except WebSocketDisconnect:
        logger.debug("WS client disconnected: session=%s", clean_session_id)
    except Exception as exc:
        logger.exception("WS endpoint error for session %s", clean_session_id)
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "server",
                    "message": str(exc),
                }
            )
        except Exception:
            pass
    finally:
        await hub.disconnect(clean_session_id, websocket)
