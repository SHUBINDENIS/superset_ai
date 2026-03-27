"""
Pydantic request/response schemas for the API layer.

These DTOs define the contract between the FastAPI API and future frontends.
They are intentionally thin wrappers over the data already produced by
backend.auth_service.AuthService.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class FrontendLogRequest(BaseModel):
    event: str = Field(..., min_length=1, max_length=120)
    level: str = Field(default="INFO", max_length=16)
    trace_id: str = Field(default="", max_length=64)
    request_id: str = Field(default="", max_length=64)
    session_id: str = Field(default="", max_length=128)
    chat_id: str = Field(default="", max_length=128)
    route: str = Field(default="", max_length=255)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class _AliasModel(BaseModel):
    """Base model that permits internal field names with public aliases."""

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    auth_db_ok: bool = False
    release_version: str = ""
    build_sha: str = ""
    build_timestamp: str = ""
    runtime: str = "nextjs-fastapi"


# ---------------------------------------------------------------------------
# Chat sessions
# ---------------------------------------------------------------------------

class ChatSettingsResponse(BaseModel):
    response_style: Literal["business", "technical"] = "business"
    detail_level: Literal["concise", "standard", "detailed"] = "standard"


class ChatSessionResponse(BaseModel):
    """Single chat session metadata."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_at: str
    is_archived: bool = False
    settings: ChatSettingsResponse = Field(default_factory=ChatSettingsResponse)


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]


class CreateChatRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class UpdateChatSettingsRequest(BaseModel):
    response_style: Literal["business", "technical"] | None = None
    detail_level: Literal["concise", "standard", "detailed"] | None = None


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
    response_style: Literal["business", "technical"] = "business"
    detail_level: Literal["concise", "standard", "detailed"] = "standard"


class SendMessageResponse(BaseModel):
    """Assistant reply returned by POST /api/chats/{session_id}/messages."""

    content: str
    role: str = "assistant"
    finish_reason: str
    model: str = ""
    session_id: str


class ClearMessagesResponse(BaseModel):
    deleted_count: int


class DeleteChatResponse(BaseModel):
    deleted_session_id: str
    was_active: bool = False
    next_active_session_id: str | None = None


# ---------------------------------------------------------------------------
# US13-US15 preview / recommend / share
# ---------------------------------------------------------------------------

class DatabaseResponse(BaseModel):
    id: int
    name: str
    backend: str


class DatabaseListResponse(BaseModel):
    databases: List[DatabaseResponse]


class DatasetResponse(_AliasModel):
    id: int
    table_name: str
    schema_name: str = Field(default="", alias="schema")
    database_name: str = ""
    database_id: int | None = None


class DatasetListResponse(BaseModel):
    datasets: List[DatasetResponse]


class DatasetColumnResponse(BaseModel):
    column_name: str
    verbose_name: str = ""
    type: str = ""


class DatasetMetadataResponse(_AliasModel):
    id: int
    table_name: str = ""
    schema_name: str = Field(default="", alias="schema")
    database_id: int | None = None
    database_name: str = ""
    columns: List[DatasetColumnResponse] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)


class PreviewRequest(_AliasModel):
    database_id: int = Field(..., ge=1)
    sql: str = Field(..., min_length=1)
    schema_name: str = Field(default="", alias="schema")
    preview_limit: int = Field(default=20, ge=1, le=500)
    dataset_id: int | None = Field(default=None, ge=1)


class PreviewColumnProfileResponse(BaseModel):
    column: str
    inferred_type: str = ""
    unit: str = ""
    non_null_count: int = 0
    distinct_count: int = 0
    sample_value: Any = None
    explanation: str = ""


class FieldExplanationResponse(BaseModel):
    column: str
    explanation: str


class PreviewResponse(_AliasModel):
    dataset_id: int | None = None
    database_id: int
    schema_name: str = Field(default="", alias="schema")
    sql_executed: str
    preview_limit: int
    rows_count: int
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[PreviewColumnProfileResponse] = Field(default_factory=list)
    field_explanations: List[FieldExplanationResponse] = Field(default_factory=list)


class RecommendVizRequest(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[PreviewColumnProfileResponse] = Field(default_factory=list)
    metric_column: str = ""
    dimension_column: str = ""
    time_column: str = ""


class RecommendationCandidateResponse(BaseModel):
    viz_type: str
    score: float
    reason: str


class RecommendationSelectedColumnsResponse(BaseModel):
    metric: str = ""
    dimension: str = ""
    time: str = ""


class RecommendVizResponse(BaseModel):
    recommended: str
    candidates: List[RecommendationCandidateResponse] = Field(default_factory=list)
    selected_columns: RecommendationSelectedColumnsResponse


class ShareWidgetRequest(BaseModel):
    dataset_id: int = Field(..., ge=1)
    dashboard_title: str = Field(default="AI Dashboard", max_length=250)
    slice_name: str = Field(default="AI Widget", max_length=250)
    viz_type: str = Field(default="table", max_length=64)
    metric_column: str = ""
    dimension_column: str = ""
    time_column: str = ""
    row_limit: int = Field(default=1000, ge=1, le=10000)
    description: str = ""


class ShareWidgetResponse(BaseModel):
    dashboard_id: int
    chart_id: int
    dashboard_url: str
    chart_url: str
    dashboard_link: str
    chart_link: str
    params: Dict[str, Any] = Field(default_factory=dict)
    viz_type: str


# ---------------------------------------------------------------------------
# US1 schema scan
# ---------------------------------------------------------------------------

class SchemaScanSummaryResponse(BaseModel):
    database_candidates_count: int = 0
    postgres_candidates_count: int = 0
    selected_databases_count: int = 0
    postgres_databases_count: int = 0
    tables_profiled_count: int = 0
    relations_detected_count: int = 0


class SchemaScanResponse(BaseModel):
    status: str = "success"
    started_at: str
    finished_at: str
    report_path: str = ""
    summary: SchemaScanSummaryResponse
    report: Dict[str, Any] = Field(default_factory=dict)
