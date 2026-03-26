"""
Pydantic request/response schemas for the API layer.

These DTOs define the contract between the FastAPI API and future frontends.
They are intentionally thin wrappers over the data already produced by
backend.auth_service.AuthService.
"""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthUserResponse(BaseModel):
    """Returned by login, register, and GET /me."""

    username: str
    role: str
    session_id: str = Field(
        default="",
        description="Active chat session id for this user.",
    )


class MessageResponse(BaseModel):
    """Generic single-message response body."""

    message: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    auth_db_ok: bool = False


# ---------------------------------------------------------------------------
# Chat sessions
# ---------------------------------------------------------------------------

class ChatSessionResponse(BaseModel):
    """Single chat session metadata."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_at: str
    is_archived: bool = False


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]


class CreateChatRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------

class ChatMessageResponse(BaseModel):
    """Single persisted chat message."""

    session_id: str
    role: str
    content: str
    created_at: str


class MessageListResponse(BaseModel):
    messages: List[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class SendMessageResponse(BaseModel):
    """Assistant reply returned by POST /api/chats/{session_id}/messages."""

    content: str
    role: str = "assistant"
    finish_reason: str
    model: str = ""
    session_id: str


class ClearMessagesResponse(BaseModel):
    deleted_count: int
