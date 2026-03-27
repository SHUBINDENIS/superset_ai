"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Eye, MessageSquare, Plus, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatEmpty } from "@/components/chat-empty";
import { ChatInput } from "@/components/chat-input";
import { ChatMessage, ChatThinking } from "@/components/chat-message";
import { useAuth } from "@/hooks/use-auth";
import { createTraceContext, extendTraceContext, logFrontendEvent } from "@/lib/observability";
import {
  useChatUI,
  useChats,
  useCreateChat,
  useMessages,
  useSendMessage,
} from "@/hooks/use-chats";
import type { ResponseStyle } from "@/lib/chats";

const RESPONSE_STYLE_STORAGE_KEY = "superset-ai-chat-response-style-v1";
const DEFAULT_RESPONSE_STYLE: ResponseStyle = "business";

function readStoredResponseStyles() {
  if (typeof window === "undefined") {
    return {} as Record<string, ResponseStyle>;
  }

  try {
    const raw = window.sessionStorage.getItem(RESPONSE_STYLE_STORAGE_KEY);
    if (!raw) {
      return {} as Record<string, ResponseStyle>;
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {} as Record<string, ResponseStyle>;
    }

    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, ResponseStyle] =>
          entry[1] === "business" || entry[1] === "technical",
      ),
    );
  } catch {
    return {} as Record<string, ResponseStyle>;
  }
}

export default function ChatPage() {
  const { user } = useAuth();
  const { activeSessionId, setActiveSessionId } = useChatUI();
  const chatsQuery = useChats();
  const createChat = useCreateChat();
  const sendMessage = useSendMessage();
  const messagesQuery = useMessages(activeSessionId);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [responseStyle, setResponseStyle] =
    useState<ResponseStyle>(DEFAULT_RESPONSE_STYLE);

  const sessions = chatsQuery.data?.sessions ?? [];
  const activeSession = useMemo(
    () => sessions.find((item) => item.session_id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );
  const messages = messagesQuery.data?.messages ?? [];
  const responseStyleSessionKey = activeSessionId || user?.session_id || "draft";
  const hasLoadedSessions = chatsQuery.data !== undefined;

  useEffect(() => {
    if (!hasLoadedSessions) {
      return;
    }

    if (!sessions.length) {
      if (activeSessionId) {
        setActiveSessionId(null);
      }
      return;
    }

    if (activeSessionId && sessions.some((item) => item.session_id === activeSessionId)) {
      return;
    }

    const authSessionId = user?.session_id ?? "";
    const preferred =
      sessions.find((item) => item.session_id === authSessionId) ?? sessions[0];
    setActiveSessionId(preferred.session_id);
  }, [activeSessionId, hasLoadedSessions, sessions, setActiveSessionId, user?.session_id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sendMessage.isPending]);

  useEffect(() => {
    const stored = readStoredResponseStyles();
    const fallbackKeys = [
      responseStyleSessionKey,
      user?.session_id || "",
      "draft",
    ].filter(Boolean);
    const nextStyle =
      fallbackKeys
        .map((key) => stored[key])
        .find((value): value is ResponseStyle => !!value) ||
      DEFAULT_RESPONSE_STYLE;
    setResponseStyle(nextStyle);
  }, [responseStyleSessionKey, user?.session_id]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = readStoredResponseStyles();
    stored[responseStyleSessionKey] = responseStyle;
    window.sessionStorage.setItem(
      RESPONSE_STYLE_STORAGE_KEY,
      JSON.stringify(stored),
    );
  }, [responseStyle, responseStyleSessionKey]);

  function handleSend(content: string) {
    const baseTrace = createTraceContext({
      sessionId: activeSessionId || user?.session_id || undefined,
      chatId: activeSessionId || undefined,
      route: "/app/chat",
    });
    logFrontendEvent(
      "chat_submit",
      {
        message_chars: content.length,
        source_window: "chat",
      },
      { traceContext: baseTrace },
    );

    if (!activeSessionId) {
      createChat.mutate(
        {
          title: "Новый чат",
          source: "chat_submit",
          traceContext: baseTrace,
        },
        {
          onSuccess: (created) => {
            sendMessage.mutate({
              sessionId: created.session_id,
              content,
              responseStyle,
              traceContext: extendTraceContext(baseTrace, {
                sessionId: created.session_id,
                chatId: created.session_id,
              }),
            });
          },
        },
      );
      return;
    }

    sendMessage.mutate({
      sessionId: activeSessionId,
      content,
      responseStyle,
      traceContext: baseTrace,
    });
  }

  const isBootstrappingChat = chatsQuery.isLoading && !activeSessionId;
  const isChatBusy = sendMessage.isPending || createChat.isPending;
  const isLoadingMessages = !!activeSessionId && messagesQuery.isLoading;

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="border-b px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              <h1 className="text-lg font-semibold">
                {activeSession?.title ?? "Чат"}
              </h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Задавайте бизнес-вопрос напрямую или начните с предпросмотра,
              если сначала нужно увидеть данные и поля.
            </p>
          </div>

          <div className="flex shrink-0 flex-col items-stretch gap-3 sm:items-end">
            <Button asChild variant="outline" size="sm">
              <Link href="/app/preview">
                <Eye className="mr-2 h-4 w-4" />
                Открыть предпросмотр
              </Link>
            </Button>

            {!sessions.length && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  createChat.mutate({
                    title: "Новый чат",
                    source: "chat_page_empty_state",
                    traceContext: createTraceContext({
                      sessionId: activeSessionId || user?.session_id || undefined,
                      chatId: activeSessionId || undefined,
                      route: "/app/chat",
                    }),
                  })
                }
                disabled={createChat.isPending}
              >
                <Plus className="mr-2 h-4 w-4" />
                Новый чат
              </Button>
            )}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border bg-card p-3">
            <p className="text-sm font-medium">Как начать</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Если вопрос уже понятен в бизнес-терминах, задайте его прямо
              здесь. Если сначала нужно понять структуру данных, откройте
              кнопку «Открыть предпросмотр» справа сверху или перейдите в
              «Сканер схем».
            </p>
          </div>
          <div className="rounded-lg border bg-card p-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <p className="text-sm font-medium">Безопасный режим</p>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Разрешены бизнес-вопросы и read-only аналитика. Опасные,
              off-topic и policy-blocked запросы будут явно помечены в чате.
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isBootstrappingChat ? (
          <div className="flex h-full items-center justify-center px-6">
            <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
              <Bot className="h-4 w-4" />
              Загружаем список чатов и активный диалог...
            </div>
          </div>
        ) : isLoadingMessages ? (
          <div className="flex h-full items-center justify-center px-6">
            <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
              Загружаем сообщения...
            </div>
          </div>
        ) : messages.length === 0 ? (
          <ChatEmpty />
        ) : (
          <div className="mx-auto flex w-full max-w-4xl flex-col py-4">
            {messages.map((message, index) => (
              <ChatMessage
                key={`${message.created_at}-${message.role}-${index}`}
                message={message}
                responseStyle={responseStyle}
              />
            ))}
            {sendMessage.isPending && <ChatThinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {messages.length === 0 && isChatBusy && (
        <div className="px-6 pb-2">
          <ChatThinking />
        </div>
      )}

      <ChatInput
        onSend={handleSend}
        disabled={isChatBusy}
        responseStyle={responseStyle}
        onResponseStyleChange={setResponseStyle}
      />
    </div>
  );
}
