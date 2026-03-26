"""
Pydantic request/response schemas for the API layer.

These DTOs define the contract between the FastAPI API and future frontends.
They are intentionally thin wrappers over the data already produced by
backend.auth_service.AuthService.
"""

from __future__ import annotations

from typing import Any

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
