"""
FastAPI dependency helpers.

Provides reusable Depends() callables for auth, services, etc.

NOTE: ``backend.auth_service`` is loaded via ``importlib.util`` to
bypass ``backend/__init__.py``, which re-exports heavy dependencies
(langchain, mcp-use, etc.) that are unnecessary for the API layer.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Cookie, HTTPException, status

# Cookie name — matches the one Streamlit already uses so that both
# transport paths share the same browser cookie when served on the
# same origin.
AUTH_COOKIE_NAME = "ai_assistant_auth_token"


# ---------------------------------------------------------------------------
# Direct module loader (avoids backend/__init__.py)
# ---------------------------------------------------------------------------

_AuthService: type | None = None


def _get_auth_service_class():
    """Load AuthService class from backend/auth_service.py without
    importing the ``backend`` package (which pulls in ai_agent, langchain, etc.)."""
    global _AuthService
    if _AuthService is not None:
        return _AuthService

    module_path = Path(__file__).resolve().parent.parent / "backend" / "auth_service.py"
    spec = importlib.util.spec_from_file_location("_auth_service_standalone", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _AuthService = mod.AuthService
    return _AuthService


# ---------------------------------------------------------------------------
# Service singletons
# ---------------------------------------------------------------------------

_auth_service_instance: Any = None


def get_auth_service():
    """Return the AuthService singleton."""
    global _auth_service_instance
    if _auth_service_instance is None:
        cls = _get_auth_service_class()
        _auth_service_instance = cls()
    return _auth_service_instance


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------

def get_current_user(
    ai_assistant_auth_token: str | None = Cookie(default=None),
) -> Dict[str, Any]:
    """Extract and validate the JWT from the auth cookie.

    Returns the validated user dict from AuthService.validate_token().
    Raises 401 if the cookie is missing or the token is invalid/expired.
    """
    token = (ai_assistant_auth_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    try:
        return get_auth_service().validate_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
