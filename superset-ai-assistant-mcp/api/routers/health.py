"""
Health check router.

Endpoint:
    GET /api/health
    HEAD /api/health
"""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import get_auth_service
from api.release import get_release_info
from api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.api_route("/api/health", methods=["GET", "HEAD"], response_model=HealthResponse)
def health() -> HealthResponse:
    auth_db_ok = False
    try:
        svc = get_auth_service()
        with svc._connect() as conn:
            conn.execute("SELECT 1")
        auth_db_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if auth_db_ok else "degraded",
        auth_db_ok=auth_db_ok,
        **get_release_info(),
    )
