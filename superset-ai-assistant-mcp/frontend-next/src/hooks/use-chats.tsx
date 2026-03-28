"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ApiError } from "@/lib/api-client";
import { publishChatSyncEvent } from "@/lib/chat-sync";
import {
  chatsApi,
  type ChatSession,
  type ChatMessage,
  type ChatSettings,
  type ChatSessionList,
  type DetailLevel,
  type MessageList,
  type ResponseStyle,
  type SendMessageResponse,
} from "@/lib/chats";
import {
  extractLinkCount,
  extendTraceContext,
  logFrontendEvent,
  type FrontendTraceContext,
} from "@/lib/observability";

interface ChatUIContextValue {
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  pendingBySessionId: Record<string, number>;
  isSessionPending: (id: string | null) => boolean;
  startSessionPending: (id: string) => void;
  finishSessionPending: (id: string) => void;
  clearSessionPending: (id: string) => void;
}

const ChatUIContext = createContext<ChatUIContextValue>({
  activeSessionId: null,
  setActiveSessionId: () => {},
  pendingBySessionId: {},
  isSessionPending: () => false,
  startSessionPending: () => {},
  finishSessionPending: () => {},
  clearSessionPending: () => {},
});

export function ChatUIProvider({ children }: { children: ReactNode }) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [pendingBySessionId, setPendingBySessionId] = useState<Record<string, number>>({});

  function startSessionPending(id: string) {
    const key = String(id || "").trim();
    if (!key) return;
    setPendingBySessionId((current) => ({
      ...current,
      [key]: (current[key] ?? 0) + 1,
    }));
  }

  function finishSessionPending(id: string) {
    const key = String(id || "").trim();
    if (!key) return;
    setPendingBySessionId((current) => {
      const nextCount = Math.max(0, (current[key] ?? 0) - 1);
      if (nextCount <= 0) {
        const { [key]: _removed, ...rest } = current;
        return rest;
      }
      return {
        ...current,
        [key]: nextCount,
      };
    });
  }

  function clearSessionPending(id: string) {
    const key = String(id || "").trim();
    if (!key) return;
    setPendingBySessionId((current) => {
      if (!(key in current)) {
        return current;
      }
      const { [key]: _removed, ...rest } = current;
      return rest;
    });
  }

  function isSessionPending(id: string | null) {
    const key = String(id || "").trim();
    if (!key) return false;
    return (pendingBySessionId[key] ?? 0) > 0;
  }

  return (
    <ChatUIContext.Provider
      value={{
        activeSessionId,
        setActiveSessionId,
        pendingBySessionId,
        isSessionPending,
        startSessionPending,
        finishSessionPending,
        clearSessionPending,
      }}
    >
      {children}
    </ChatUIContext.Provider>
  );
}

export function useChatUI() {
  return useContext(ChatUIContext);
}

const CHATS_KEY = ["chats"] as const;
const AUTH_KEY = ["auth", "me"] as const;

function messagesKey(sessionId: string | null) {
  return ["chats", sessionId, "messages"] as const;
}

function upsertChatSession(
  current: ChatSessionList | undefined,
  session: ChatSession,
): ChatSessionList {
  const sessions = current?.sessions ?? [];
  return {
    sessions: [
      session,
      ...sessions.filter((item) => item.session_id !== session.session_id),
    ],
  };
}

function replaceChatSession(
  current: ChatSessionList | undefined,
  session: ChatSession,
): ChatSessionList {
  const sessions = current?.sessions ?? [];
  let replaced = false;
  const nextSessions = sessions.map((item) => {
    if (item.session_id !== session.session_id) {
      return item;
    }
    replaced = true;
    return session;
  });
  return {
    sessions: replaced ? nextSessions : [session, ...nextSessions],
  };
}

function buildErrorMessage(
  message: string,
  sessionId: string,
  responseStyle?: ResponseStyle,
  detailLevel?: DetailLevel,
): ChatMessage {
  return {
    role: "assistant",
    content: `Ошибка при обработке запроса: ${message}`,
    session_id: sessionId,
    created_at: new Date().toISOString(),
    finish_reason: "error",
    response_style: responseStyle,
    detail_level: detailLevel,
  };
}

export function useChats(options?: { enabled?: boolean }) {
  return useQuery<ChatSessionList>({
    queryKey: CHATS_KEY,
    queryFn: chatsApi.list,
    staleTime: 30_000,
    enabled: options?.enabled ?? true,
  });
}

export function useMessages(sessionId: string | null) {
  return useQuery<MessageList>({
    queryKey: messagesKey(sessionId),
    queryFn: () => chatsApi.listMessages(sessionId!),
    enabled: !!sessionId,
    staleTime: 10_000,
  });
}

export function useCreateChat() {
  const qc = useQueryClient();
  const { setActiveSessionId } = useChatUI();

  return useMutation({
    mutationFn: (variables: {
      title?: string | null;
      traceContext?: Partial<FrontendTraceContext>;
      source?: string;
    }) => chatsApi.create(variables.title, variables.traceContext),
    onSuccess: (created, variables) => {
      qc.setQueryData<ChatSessionList>(CHATS_KEY, (current) =>
        upsertChatSession(current, created),
      );
      qc.setQueryData<MessageList>(
        messagesKey(created.session_id),
        (current) => current ?? { messages: [] },
      );
      setActiveSessionId(created.session_id);
      logFrontendEvent(
        "chat_new",
        { source: variables.source || "unknown" },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: created.session_id,
            chatId: created.session_id,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_created",
        sessionId: created.session_id,
      });
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}

export function useRenameChat() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      sessionId,
      title,
      traceContext,
    }: {
      sessionId: string;
      title: string;
      traceContext?: Partial<FrontendTraceContext>;
    }) => chatsApi.rename(sessionId, title, traceContext),
    onSuccess: (updated, variables) => {
      qc.setQueryData<ChatSessionList>(CHATS_KEY, (current) =>
        replaceChatSession(current, updated),
      );
      logFrontendEvent(
        "chat_rename",
        { title_chars: variables.title.trim().length },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_renamed",
        sessionId: variables.sessionId,
      });
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}

export function useActivateChat() {
  const qc = useQueryClient();
  const { setActiveSessionId } = useChatUI();

  return useMutation({
    mutationFn: (variables: {
      sessionId: string;
      traceContext?: Partial<FrontendTraceContext>;
    }) => chatsApi.activate(variables.sessionId, variables.traceContext),
    onMutate: async (sessionId) => {
      setActiveSessionId(sessionId.sessionId);
    },
    onSuccess: (session, variables) => {
      setActiveSessionId(session.session_id);
      qc.setQueryData<ChatSessionList>(CHATS_KEY, (current) =>
        replaceChatSession(current, session),
      );
      logFrontendEvent(
        "chat_switch",
        { target_session_id: session.session_id },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: session.session_id,
            chatId: session.session_id,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_activated",
        sessionId: session.session_id,
      });
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}

export function useClearMessages() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (variables: {
      sessionId: string;
      traceContext?: Partial<FrontendTraceContext>;
    }) => chatsApi.clearMessages(variables.sessionId, variables.traceContext),
    onSuccess: (_data, variables) => {
      qc.setQueryData<MessageList>(messagesKey(variables.sessionId), { messages: [] });
      logFrontendEvent(
        "chat_clear",
        { cleared_session_id: variables.sessionId },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_cleared",
        sessionId: variables.sessionId,
      });
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}

export function useDeleteChat() {
  const qc = useQueryClient();
  const { clearSessionPending, setActiveSessionId } = useChatUI();

  return useMutation({
    mutationFn: (variables: {
      sessionId: string;
      traceContext?: Partial<FrontendTraceContext>;
    }) => chatsApi.deleteChat(variables.sessionId, variables.traceContext),
    onMutate: async (variables) => {
      logFrontendEvent(
        "chat_delete_requested",
        { deleted_session_id: variables.sessionId },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
    },
    onSuccess: (data, variables) => {
      qc.removeQueries({ queryKey: messagesKey(variables.sessionId) });
      qc.setQueryData<ChatSessionList>(CHATS_KEY, (current) => ({
        sessions: (current?.sessions ?? []).filter(
          (item) => item.session_id !== variables.sessionId,
        ),
      }));
      clearSessionPending(variables.sessionId);
      if (data.was_active) {
        setActiveSessionId(data.next_active_session_id || null);
      }
      logFrontendEvent(
        "chat_delete_success",
        {
          deleted_session_id: variables.sessionId,
          was_active: data.was_active,
          next_active_session_id: data.next_active_session_id || "",
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_deleted",
        sessionId: variables.sessionId,
      });
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
      qc.invalidateQueries({ queryKey: AUTH_KEY });
    },
    onError: (error, variables) => {
      logFrontendEvent(
        "chat_delete_failed",
        {
          deleted_session_id: variables.sessionId,
          error_message: error.message,
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
    },
  });
}

type SendMessageVariables = {
  sessionId: string;
  content: string;
  responseStyle: ResponseStyle;
  detailLevel: DetailLevel;
  traceContext?: Partial<FrontendTraceContext>;
};

type SendMessageContext = {
  previous?: MessageList;
  optimisticUserMessage: ChatMessage;
};

type UpdateChatSettingsVariables = {
  sessionId: string;
  settings: Partial<ChatSettings>;
  traceContext?: Partial<FrontendTraceContext>;
};

type UpdateChatSettingsContext = {
  previous?: ChatSessionList;
};

export function useSendMessage() {
  const qc = useQueryClient();
  const { finishSessionPending, startSessionPending } = useChatUI();

  return useMutation<
    SendMessageResponse,
    ApiError,
    SendMessageVariables,
    SendMessageContext
  >({
    mutationFn: ({ sessionId, content, responseStyle, detailLevel, traceContext }) =>
      chatsApi.sendMessage(
        sessionId,
        content,
        responseStyle,
        detailLevel,
        traceContext,
      ),

    onMutate: async ({ sessionId, content }) => {
      const key = messagesKey(sessionId);
      await qc.cancelQueries({ queryKey: key });
      startSessionPending(sessionId);
      const previous = qc.getQueryData<MessageList>(key);
      const optimisticUserMessage: ChatMessage = {
        role: "user",
        content,
        session_id: sessionId,
        created_at: new Date().toISOString(),
      };

      qc.setQueryData<MessageList>(key, (old) => ({
        messages: [...(old?.messages ?? []), optimisticUserMessage],
      }));

      return { previous, optimisticUserMessage };
    },

    onSuccess: (reply, { sessionId, traceContext }) => {
      const key = messagesKey(sessionId);
      qc.setQueryData<MessageList>(key, (old) => ({
        messages: [
          ...(old?.messages ?? []),
          {
            role: "assistant",
            content: reply.content,
            session_id: reply.session_id,
            created_at: new Date().toISOString(),
            finish_reason: reply.finish_reason,
            model: reply.model,
            response_style: reply.response_style,
            detail_level: reply.detail_level,
            artifacts: reply.artifacts ?? [],
          },
        ],
      }));
      const resolvedTrace = extendTraceContext(traceContext, {
        sessionId,
        chatId: sessionId,
        route: "/app/chat",
      });
      logFrontendEvent(
        "assistant_reply_received",
        {
          finish_reason: reply.finish_reason,
          status: reply.finish_reason === "blocked" ? "blocked" : "ok",
          link_count: extractLinkCount(reply.content),
          artifact_count: reply.artifacts?.length ?? 0,
          message_chars: reply.content.length,
        },
        { traceContext: resolvedTrace },
      );
      if (reply.finish_reason === "blocked") {
        logFrontendEvent(
          "blocked_response_received",
          { message_chars: reply.content.length },
          { traceContext: resolvedTrace },
        );
      }
      publishChatSyncEvent({
        type: "chat_messages_updated",
        sessionId,
      });
    },

    onError: (
      error,
      { sessionId, responseStyle, detailLevel, traceContext },
      _context,
    ) => {
      qc.setQueryData<MessageList>(messagesKey(sessionId), (current) => ({
        messages: [
          ...(current?.messages ?? []),
          buildErrorMessage(error.message, sessionId, responseStyle, detailLevel),
        ],
      }));
      logFrontendEvent(
        "assistant_reply_error",
        { status: "error", error_message: error.message },
        {
          traceContext: extendTraceContext(traceContext, {
            sessionId,
            chatId: sessionId,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_messages_updated",
        sessionId,
      });
    },

    onSettled: (_data, error, variables) => {
      finishSessionPending(variables.sessionId);
      if (!error) {
        qc.invalidateQueries({ queryKey: messagesKey(variables.sessionId) });
      }
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}

export function useUpdateChatSettings() {
  const qc = useQueryClient();

  return useMutation<
    ChatSession,
    ApiError,
    UpdateChatSettingsVariables,
    UpdateChatSettingsContext
  >({
    mutationFn: (variables) =>
      chatsApi.updateSettings(
        variables.sessionId,
        variables.settings,
        variables.traceContext,
      ),
    onMutate: async (variables) => {
      await qc.cancelQueries({ queryKey: CHATS_KEY });
      const previous = qc.getQueryData<ChatSessionList>(CHATS_KEY);
      if (previous) {
        const current = previous.sessions.find(
          (item) => item.session_id === variables.sessionId,
        );
        if (current) {
          qc.setQueryData<ChatSessionList>(CHATS_KEY, replaceChatSession(previous, {
            ...current,
            settings: {
              ...current.settings,
              ...variables.settings,
            },
          }));
        }
      }
      return { previous };
    },
    onSuccess: (updated, variables) => {
      qc.setQueryData<ChatSessionList>(CHATS_KEY, (current) =>
        replaceChatSession(current, updated),
      );
      logFrontendEvent(
        "chat_settings_update",
        {
          response_style: updated.settings.response_style,
          detail_level: updated.settings.detail_level,
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: variables.sessionId,
            chatId: variables.sessionId,
            route: "/app/chat",
          }),
        },
      );
      publishChatSyncEvent({
        type: "chat_settings_updated",
        sessionId: variables.sessionId,
      });
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        qc.setQueryData(CHATS_KEY, context.previous);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: CHATS_KEY, exact: true });
    },
  });
}
