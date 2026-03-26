"""
Thin FastAPI router for frontend-side structured log ingestion.

The Next.js UI sends small privacy-safe event envelopes here so they land in
the same JSONL frontend log file as the Streamlit UI.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from api.deps import (
    bind_request_log_context,
    emit_frontend_log_event,
    get_optional_current_user,
)
from api.schemas import FrontendLogRequest, MessageResponse

router = APIRouter(prefix="/api/frontend", tags=["frontend-observability"])


@router.post("/logs", response_model=MessageResponse)
def ingest_frontend_log(
    body: FrontendLogRequest,
    request: Request,
    current_user: Dict[str, Any] | None = Depends(get_optional_current_user),
) -> MessageResponse:
    with bind_request_log_context(
        request,
        current_user,
        trace_id=body.trace_id,
        request_id=body.request_id,
        session_id=body.session_id,
        chat_id=body.chat_id,
    ):
        emit_frontend_log_event(
            body.event,
            level=body.level,
            source="nextjs",
            route=body.route,
            metadata=body.metadata,
            session_id=body.session_id,
            chat_id=body.chat_id,
        )
    return MessageResponse(message="Logged.")
