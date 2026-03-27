"""
Chat session & message router.

Endpoints:
    GET    /api/chats                          – list user's chat sessions
    POST   /api/chats                          – create a new chat session
    PATCH  /api/chats/{session_id}             – rename a chat session
    POST   /api/chats/{session_id}/activate    – mark a chat as active
    GET    /api/chats/{session_id}/messages     – list messages in a session
    DELETE /api/chats/{session_id}/messages     – clear messages in a session
    POST   /api/chats/{session_id}/messages     – send a message (runs agent)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.deps import (
    bind_request_log_context,
    get_agent_session_manager,
    get_auth_service,
    get_current_user,
)
from api.schemas import (
    ChatMessageResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ClearMessagesResponse,
    DeleteChatResponse,
    CreateChatRequest,
    MessageListResponse,
    RenameChatRequest,
    SendMessageRequest,
    SendMessageResponse,
    UpdateChatSettingsRequest,
)

router = APIRouter(prefix="/api/chats", tags=["chats"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_or_404(auth_service, username: str, session_id: str) -> Dict[str, Any]:
    """Fetch a chat session or raise 404."""
    session = auth_service.get_chat_session(username=username, session_id=session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    return session


def _normalize_response_style(value: Any) -> str:
    return "technical" if str(value or "").strip().lower() == "technical" else "business"


def _normalize_detail_level(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"concise", "detailed"}:
        return normalized
    return "standard"


# ---------------------------------------------------------------------------
# Chat session CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=ChatSessionListResponse)
def list_chats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ChatSessionListResponse:
    """Return all non-archived chat sessions for the authenticated user."""
    sessions = auth_service.list_chat_sessions(username=current_user["username"])
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(**s) for s in sessions],
    )


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    body: CreateChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ChatSessionResponse:
    """Create a new chat session."""
    created = auth_service.create_chat_session(
        current_user["username"],
        body.title,
    )
    return ChatSessionResponse(**created)


@router.patch("/{session_id}", response_model=ChatSessionResponse)
def rename_chat(
    session_id: str,
    body: RenameChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ChatSessionResponse:
    """Rename an existing chat session."""
    try:
        updated = auth_service.rename_chat_session(
            username=current_user["username"],
            session_id=session_id,
            title=body.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ChatSessionResponse(**updated)


@router.patch("/{session_id}/settings", response_model=ChatSessionResponse)
def update_chat_settings(
    session_id: str,
    body: UpdateChatSettingsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ChatSessionResponse:
    """Update per-chat settings such as response style and detail level."""
    try:
        updated = auth_service.update_chat_session_settings(
            username=current_user["username"],
            session_id=session_id,
            settings=body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ChatSessionResponse(**updated)


@router.post("/{session_id}/activate", response_model=ChatSessionResponse)
def activate_chat(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ChatSessionResponse:
    """Mark an existing chat session as active for future auth restore."""
    try:
        updated = auth_service.set_active_chat_session(
            username=current_user["username"],
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ChatSessionResponse(**updated)


@router.delete("/{session_id}", response_model=DeleteChatResponse)
async def delete_chat(
    session_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
    agent_manager=Depends(get_agent_session_manager),
) -> DeleteChatResponse:
    """Archive a chat session and remove it from the active list."""
    with bind_request_log_context(
        request,
        current_user,
        session_id=session_id,
        chat_id=session_id,
    ):
        try:
            deleted = auth_service.archive_chat_session(
                username=current_user["username"],
                session_id=session_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        try:
            await agent_manager.close_session(session_id)
        except Exception as exc:
            logger.warning(
                "Failed to close in-memory chat session after archive: session_id=%s error=%r",
                session_id,
                exc,
            )

        return DeleteChatResponse(**deleted)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/{session_id}/messages", response_model=MessageListResponse)
def list_messages(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> MessageListResponse:
    """Return persisted messages for a chat session."""
    _session_or_404(auth_service, current_user["username"], session_id)
    messages = auth_service.list_chat_history(
        username=current_user["username"],
        session_id=session_id,
    )
    return MessageListResponse(
        messages=[ChatMessageResponse(**m) for m in messages],
    )


@router.delete(
    "/{session_id}/messages",
    response_model=ClearMessagesResponse,
)
def clear_messages(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
) -> ClearMessagesResponse:
    """Delete all messages in a chat session."""
    _session_or_404(auth_service, current_user["username"], session_id)
    deleted = auth_service.clear_chat_history(
        username=current_user["username"],
        session_id=session_id,
    )
    return ClearMessagesResponse(deleted_count=deleted)


@router.post(
    "/{session_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
    agent_manager=Depends(get_agent_session_manager),
) -> SendMessageResponse:
    """Send a user message and receive the assistant reply.

    Flow:
        1. Verify session ownership.
        2. Persist the user message.
        3. Load full conversation history for context.
        4. Get/create agent for the session.
        5. Run ``agent.chat(messages)`` (may block while LLM processes).
        6. Persist the assistant reply.
        7. Return the reply including ``finish_reason``.
    """
    username = current_user["username"]

    # 1. Verify session exists and belongs to user
    session = _session_or_404(auth_service, username, session_id)
    session_settings = session.get("settings", {}) if isinstance(session, dict) else {}
    resolved_response_style = _normalize_response_style(
        body.response_style
        or session_settings.get("response_style")
        or "business"
    )
    resolved_detail_level = _normalize_detail_level(
        body.detail_level
        or session_settings.get("detail_level")
        or "standard"
    )

    # 2. Persist user message
    auth_service.save_chat_message(
        username=username,
        session_id=session_id,
        role="user",
        content=body.content,
    )

    # 3. Load full history (includes the message just saved)
    history = auth_service.list_chat_history(
        username=username,
        session_id=session_id,
    )
    messages = [dict(item) for item in history]

    with bind_request_log_context(
        request,
        current_user,
        session_id=session_id,
        chat_id=session_id,
    ):
        # 4. Get or create agent for this session
        agent = await agent_manager.get_or_create_agent(session_id, owner=username)

        # 5. Run agent
        try:
            reply = await agent.chat(
                messages,
                response_style=resolved_response_style,
                detail_level=resolved_detail_level,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Agent processing failed: {exc}",
            ) from exc

        normalized_reply_style = _normalize_response_style(
            reply.get("response_style") or resolved_response_style
        )
        normalized_reply_detail = _normalize_detail_level(
            reply.get("detail_level") or resolved_detail_level
        )

        try:
            # 6. Persist assistant reply
            auth_service.save_chat_message(
                username=username,
                session_id=session_id,
                role="assistant",
                content=reply.get("content", ""),
                metadata={
                    "finish_reason": reply.get("finish_reason", "stop"),
                    "model": reply.get("model", ""),
                    "response_style": normalized_reply_style,
                    "detail_level": normalized_reply_detail,
                    "artifacts": reply.get("artifacts", []),
                },
            )

            # 7. Return
            return SendMessageResponse(
                content=reply.get("content", ""),
                role=reply.get("role", "assistant"),
                finish_reason=reply.get("finish_reason", "stop"),
                model=reply.get("model", ""),
                session_id=session_id,
                response_style=normalized_reply_style,
                detail_level=normalized_reply_detail,
                artifacts=reply.get("artifacts", []),
            )
        except Exception as exc:
            logger.exception(
                "Failed to persist or serialize assistant reply for session %s",
                session_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Assistant reply handling failed: {exc}",
            ) from exc
