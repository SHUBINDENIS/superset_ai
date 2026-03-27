/**
 * Chat session & message API functions.
 *
 * Shapes match the Pydantic DTOs in `api/schemas.py`.
 */

import { apiFetch } from "./api-client";
import type { FrontendTraceContext } from "./observability";

/* ------------------------------------------------------------------ */
/* Types                                                              */
/* ------------------------------------------------------------------ */

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string;
  is_archived: boolean;
  settings: ChatSettings;
}

export interface ChatSessionList {
  sessions: ChatSession[];
}

export interface ChatMessage {
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  finish_reason?: string;
}

export interface MessageList {
  messages: ChatMessage[];
}

export interface SendMessageResponse {
  content: string;
  role: string;
  finish_reason: string;
  model: string;
  session_id: string;
}

export type ResponseStyle = "business" | "technical";
export type DetailLevel = "concise" | "standard" | "detailed";

export interface ChatSettings {
  response_style: ResponseStyle;
  detail_level: DetailLevel;
}

export interface DeleteChatResponse {
  deleted_session_id: string;
  was_active: boolean;
  next_active_session_id: string | null;
}

/* ------------------------------------------------------------------ */
/* API calls                                                          */
/* ------------------------------------------------------------------ */

export const chatsApi = {
  /** List all chat sessions for the authenticated user. */
  list: () => apiFetch<ChatSessionList>("/chats"),

  /** Create a new chat session. */
  create: (
    title?: string | null,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<ChatSession>("/chats", {
      method: "POST",
      traceContext,
      body: JSON.stringify({ title }),
    }),

  /** Rename a chat session. */
  rename: (
    sessionId: string,
    title: string,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<ChatSession>(`/chats/${sessionId}`, {
      method: "PATCH",
      traceContext,
      body: JSON.stringify({ title }),
    }),

  /** Mark a chat session as active for future auth restore. */
  activate: (
    sessionId: string,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<ChatSession>(`/chats/${sessionId}/activate`, {
      method: "POST",
      traceContext,
    }),

  /** List messages for a chat session. */
  listMessages: (sessionId: string) =>
    apiFetch<MessageList>(`/chats/${sessionId}/messages`),

  /** Clear all messages in a chat session. */
  clearMessages: (
    sessionId: string,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<{ deleted_count: number }>(`/chats/${sessionId}/messages`, {
      method: "DELETE",
      traceContext,
    }),

  /** Archive a chat session and remove it from the visible list. */
  deleteChat: (
    sessionId: string,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<DeleteChatResponse>(`/chats/${sessionId}`, {
      method: "DELETE",
      traceContext,
    }),

  /** Update per-chat settings. */
  updateSettings: (
    sessionId: string,
    settings: Partial<ChatSettings>,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<ChatSession>(`/chats/${sessionId}/settings`, {
      method: "PATCH",
      traceContext,
      body: JSON.stringify(settings),
    }),

  /** Send a user message and receive the assistant reply. */
  sendMessage: (
    sessionId: string,
    content: string,
    responseStyle: ResponseStyle,
    detailLevel: DetailLevel,
    traceContext?: Partial<FrontendTraceContext>,
  ) =>
    apiFetch<SendMessageResponse>(`/chats/${sessionId}/messages`, {
      method: "POST",
      traceContext,
      body: JSON.stringify({
        content,
        response_style: responseStyle,
        detail_level: detailLevel,
      }),
    }),
};
