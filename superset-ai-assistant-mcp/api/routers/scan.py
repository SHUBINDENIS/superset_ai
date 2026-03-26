"""
Thin FastAPI router for the US1 schema scan flow.

The endpoint wraps the existing synchronous-on-request scan behavior used by
the Streamlit UI without changing the underlying profiler logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.deps import bind_request_log_context, get_current_user, get_us1_scan_runner
from api.schemas import SchemaScanResponse, SchemaScanSummaryResponse

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("", response_model=SchemaScanResponse)
async def run_schema_scan(
    request: Request,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    scan_runner=Depends(get_us1_scan_runner),
) -> SchemaScanResponse:
    started_at = datetime.now(timezone.utc).isoformat()
    with bind_request_log_context(request, _current_user):
        try:
            result = await scan_runner()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Schema scan returned an empty or invalid result.",
        )

    return SchemaScanResponse(
        status="success",
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        report_path=str(result.get("report_path", "")),
        summary=SchemaScanSummaryResponse(**dict(result.get("summary") or {})),
        report=dict(result.get("report") or {}),
    )
