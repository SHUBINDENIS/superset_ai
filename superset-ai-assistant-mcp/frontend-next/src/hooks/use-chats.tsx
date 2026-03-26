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
  type ChatMessage,
  type ChatSessionList,
  type MessageList,
  type SendMessageResponse,
} from "@/lib/chats";

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

function messagesKey(sessionId: string | null) {
  return ["chats", sessionId, "messages"] as const;
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
    mutationFn: (title?: string | null) => chatsApi.create(title),
    onSuccess: (created) => {
      setActiveSessionId(created.session_id);
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}

export function useRenameChat() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      chatsApi.rename(sessionId, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}

export function useActivateChat() {
  const qc = useQueryClient();
  const { setActiveSessionId } = useChatUI();

  return useMutation({
    mutationFn: (sessionId: string) => chatsApi.activate(sessionId),
    onMutate: async (sessionId) => {
      setActiveSessionId(sessionId);
    },
    onSuccess: (session) => {
      setActiveSessionId(session.session_id);
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}

export function useClearMessages() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) => chatsApi.clearMessages(sessionId),
    onSuccess: (_, sessionId) => {
      qc.setQueryData<MessageList>(messagesKey(sessionId), { messages: [] });
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}

type SendMessageVariables = {
  sessionId: string;
  content: string;
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
    mutationFn: ({ sessionId, content }) =>
      chatsApi.sendMessage(sessionId, content),

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

    onSuccess: (reply, { sessionId }) => {
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
    },

    onError: (error, { sessionId }, context) => {
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
    },

    onSettled: (_data, error, variables) => {
      if (!error) {
        qc.invalidateQueries({ queryKey: messagesKey(variables.sessionId) });
      }
      qc.invalidateQueries({ queryKey: CHATS_KEY });
    },
  });
}
