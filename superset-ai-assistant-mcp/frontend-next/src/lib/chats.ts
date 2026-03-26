/**
 * Chat session & message API functions.
 *
 * Shapes match the Pydantic DTOs in `api/schemas.py`.
 */

import { apiFetch } from "./api-client";

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

/* ------------------------------------------------------------------ */
/* API calls                                                          */
/* ------------------------------------------------------------------ */

export const chatsApi = {
  /** List all chat sessions for the authenticated user. */
  list: () => apiFetch<ChatSessionList>("/chats"),

  /** Create a new chat session. */
  create: (title?: string | null) =>
    apiFetch<ChatSession>("/chats", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  /** Rename a chat session. */
  rename: (sessionId: string, title: string) =>
    apiFetch<ChatSession>(`/chats/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  /** Mark a chat session as active for future auth restore. */
  activate: (sessionId: string) =>
    apiFetch<ChatSession>(`/chats/${sessionId}/activate`, {
      method: "POST",
    }),

  /** List messages for a chat session. */
  listMessages: (sessionId: string) =>
    apiFetch<MessageList>(`/chats/${sessionId}/messages`),

  /** Clear all messages in a chat session. */
  clearMessages: (sessionId: string) =>
    apiFetch<{ deleted_count: number }>(`/chats/${sessionId}/messages`, {
      method: "DELETE",
    }),

  /** Send a user message and receive the assistant reply. */
  sendMessage: (sessionId: string, content: string) =>
    apiFetch<SendMessageResponse>(`/chats/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};
