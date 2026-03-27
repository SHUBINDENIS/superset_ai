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
import {
  chatsApi,
  type ChatSession,
  type ChatMessage,
  type ChatSessionList,
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
}

const ChatUIContext = createContext<ChatUIContextValue>({
  activeSessionId: null,
  setActiveSessionId: () => {},
});

export function ChatUIProvider({ children }: { children: ReactNode }) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  return (
    <ChatUIContext.Provider value={{ activeSessionId, setActiveSessionId }}>
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

function buildErrorMessage(message: string, sessionId: string): ChatMessage {
  return {
    role: "assistant",
    content: `Ошибка при обработке запроса: ${message}`,
    session_id: sessionId,
    created_at: new Date().toISOString(),
    finish_reason: "error",
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
      qc.invalidateQueries({ queryKey: CHATS_KEY });
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
    onSuccess: (_updated, variables) => {
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
      qc.invalidateQueries({ queryKey: CHATS_KEY });
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
      qc.invalidateQueries({ queryKey: CHATS_KEY });
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
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}

export function useDeleteChat() {
  const qc = useQueryClient();
  const { setActiveSessionId } = useChatUI();

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
      qc.invalidateQueries({ queryKey: CHATS_KEY });
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
  traceContext?: Partial<FrontendTraceContext>;
};

type SendMessageContext = {
  previous?: MessageList;
  optimisticUserMessage: ChatMessage;
};

export function useSendMessage() {
  const qc = useQueryClient();

  return useMutation<
    SendMessageResponse,
    ApiError,
    SendMessageVariables,
    SendMessageContext
  >({
    mutationFn: ({ sessionId, content, responseStyle, traceContext }) =>
      chatsApi.sendMessage(sessionId, content, responseStyle, traceContext),

    onMutate: async ({ sessionId, content }) => {
      const key = messagesKey(sessionId);
      await qc.cancelQueries({ queryKey: key });
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
    },

    onError: (error, { sessionId, traceContext }, context) => {
      const previousMessages = context?.previous?.messages ?? [];
      const optimisticUserMessage = context?.optimisticUserMessage;
      const nextMessages = optimisticUserMessage
        ? [
            ...previousMessages,
            optimisticUserMessage,
            buildErrorMessage(error.message, sessionId),
          ]
        : [...previousMessages, buildErrorMessage(error.message, sessionId)];
      qc.setQueryData<MessageList>(messagesKey(sessionId), {
        messages: nextMessages,
      });
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
    },

    onSettled: (_data, error, variables) => {
      if (!error) {
        qc.invalidateQueries({ queryKey: messagesKey(variables.sessionId) });
      }
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}
