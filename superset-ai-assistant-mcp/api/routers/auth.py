"""
Auth API router.

Endpoints:
    POST /api/auth/register
    POST /api/auth/login
    POST /api/auth/logout
    GET  /api/auth/me
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.deps import AUTH_COOKIE_NAME, get_auth_service, get_current_user
from api.schemas import AuthUserResponse, LoginRequest, MessageResponse, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _jwt_ttl_seconds() -> int:
    hours = max(1, int(os.getenv("AUTH_JWT_TTL_HOURS", "12")))
    return hours * 3600


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=_jwt_ttl_seconds(),
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,  # Set True when served behind HTTPS
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )


@router.post(
    "/register",
    response_model=AuthUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    body: RegisterRequest,
    response: Response,
    auth_service=Depends(get_auth_service),
) -> AuthUserResponse:
    try:
        created = auth_service.register_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # Auto-login after registration
    try:
        auth_result = auth_service.authenticate_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration succeeded but auto-login failed.",
        ) from exc

    _set_auth_cookie(response, auth_result["auth_token"])

    return AuthUserResponse(
        username=auth_result["username"],
        role=auth_result["role"],
        session_id=auth_result.get("session_id", ""),
    )


@router.post("/login", response_model=AuthUserResponse)
def login(
    body: LoginRequest,
    response: Response,
    auth_service=Depends(get_auth_service),
) -> AuthUserResponse:
    try:
        auth_result = auth_service.authenticate_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _set_auth_cookie(response, auth_result["auth_token"])

    return AuthUserResponse(
        username=auth_result["username"],
        role=auth_result["role"],
        session_id=auth_result.get("session_id", ""),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    _clear_auth_cookie(response)
    return MessageResponse(message="Logged out.")


@router.get("/me", response_model=AuthUserResponse)
def me(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AuthUserResponse:
    return AuthUserResponse(
        username=current_user["username"],
        role=current_user["role"],
        session_id=current_user.get("session_id", ""),
    )
