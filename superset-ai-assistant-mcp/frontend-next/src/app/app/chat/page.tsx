"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpenText, Bot, MessageSquare, Plus, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatControlsBar } from "@/components/chat-controls-bar";
import { ChatEmpty } from "@/components/chat-empty";
import { ChatHelpDrawer } from "@/components/chat-help-drawer";
import { ChatInput } from "@/components/chat-input";
import { ChatMessage, ChatThinking } from "@/components/chat-message";
import { useAppShellState } from "@/components/app-shell-state";
import { useAuth } from "@/hooks/use-auth";
import { subscribeChatSyncEvents } from "@/lib/chat-sync";
import { createTraceContext, extendTraceContext, logFrontendEvent } from "@/lib/observability";
import {
  useChatUI,
  useChats,
  useCreateChat,
  useMessages,
  useSendMessage,
  useUpdateChatSettings,
} from "@/hooks/use-chats";
import type { ChatSettings, DetailLevel, ResponseStyle } from "@/lib/chats";

const DEFAULT_CHAT_SETTINGS: ChatSettings = {
  response_style: "business",
  detail_level: "standard",
};

function settingsEqual(left: ChatSettings, right: ChatSettings) {
  return (
    left.response_style === right.response_style &&
    left.detail_level === right.detail_level
  );
}

export default function ChatPage() {
  const settingsCollapseStorageKey = "superset-ai:chat-settings-collapsed";
  const { user } = useAuth();
  const { isMobileViewport, mobileChatHelperHidden } = useAppShellState();
  const queryClient = useQueryClient();
  const {
    activeSessionId,
    isSessionPending,
    pendingBySessionId,
    setActiveSessionId,
  } = useChatUI();
  const chatsQuery = useChats();
  const createChat = useCreateChat();
  const sendMessage = useSendMessage();
  const updateChatSettings = useUpdateChatSettings();
  const messagesQuery = useMessages(activeSessionId);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [settingsCollapsed, setSettingsCollapsed] = useState(false);
  const [draftSettingsBySessionId, setDraftSettingsBySessionId] = useState<
    Record<string, ChatSettings>
  >({});
  const [savingSettingsBySessionId, setSavingSettingsBySessionId] = useState<
    Record<string, boolean>
  >({});
  const queuedSettingsBySessionIdRef = useRef<Record<string, ChatSettings | undefined>>(
    {},
  );
  const inFlightSettingsBySessionIdRef = useRef<Record<string, boolean>>({});

  const sessions = chatsQuery.data?.sessions ?? [];
  const activeSession = useMemo(
    () => sessions.find((item) => item.session_id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );
  const messages = messagesQuery.data?.messages ?? [];
  const hasLoadedSessions = chatsQuery.data !== undefined;
  const activeDraftSettings = activeSessionId
    ? draftSettingsBySessionId[activeSessionId]
    : draftSettingsBySessionId["__new__"];
  const activeSettings =
    activeDraftSettings ??
    activeSession?.settings ??
    DEFAULT_CHAT_SETTINGS;
  const activeResponseStyle = activeSettings.response_style;
  const activeDetailLevel = activeSettings.detail_level;
  const activeSessionPending = isSessionPending(activeSessionId);
  const activeSessionSettingsSaving = activeSessionId
    ? Boolean(savingSettingsBySessionId[activeSessionId])
    : false;
  const otherPendingCount = Object.entries(pendingBySessionId).filter(
    ([sessionId, count]) => sessionId !== activeSessionId && count > 0,
  ).length;
  const helperAreaHidden = isMobileViewport && mobileChatHelperHidden;

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
  }, [messages.length, activeSessionPending]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const stored = window.localStorage.getItem(settingsCollapseStorageKey);
      if (stored === "true" || stored === "false") {
        setSettingsCollapsed(stored === "true");
        return;
      }
    } catch {
      // Ignore storage issues and fall back to viewport default.
    }
    setSettingsCollapsed(window.innerWidth < 768);
  }, [settingsCollapseStorageKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(
        settingsCollapseStorageKey,
        settingsCollapsed ? "true" : "false",
      );
    } catch {
      // Collapse preference is non-critical.
    }
  }, [settingsCollapseStorageKey, settingsCollapsed]);

  useEffect(() => {
    return subscribeChatSyncEvents((event) => {
      if (event.type === "chat_deleted" && activeSessionId === event.sessionId) {
        setActiveSessionId(null);
      }
      queryClient.invalidateQueries({ queryKey: ["chats"], exact: true });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({
        queryKey: ["chats", event.sessionId, "messages"],
      });
      if (event.type === "chat_deleted") {
        queryClient.removeQueries({
          queryKey: ["chats", event.sessionId, "messages"],
        });
      }
    });
  }, [activeSessionId, queryClient, setActiveSessionId]);

  useEffect(() => {
    setDraftSettingsBySessionId((current) => {
      const validSessionIds = new Set(sessions.map((item) => item.session_id));
      let changed = false;
      const next: Record<string, ChatSettings> = {};
      for (const [sessionId, settings] of Object.entries(current)) {
        if (sessionId === "__new__") {
          next[sessionId] = settings;
          continue;
        }
        if (!validSessionIds.has(sessionId)) {
          changed = true;
          continue;
        }
        const serverSettings =
          sessions.find((item) => item.session_id === sessionId)?.settings ??
          DEFAULT_CHAT_SETTINGS;
        if (
          !inFlightSettingsBySessionIdRef.current[sessionId] &&
          settingsEqual(settings, serverSettings)
        ) {
          changed = true;
          continue;
        }
        next[sessionId] = settings;
      }
      return changed ? next : current;
    });
  }, [sessions]);

  function setSettingsSaving(sessionId: string, saving: boolean) {
    setSavingSettingsBySessionId((current) => {
      const key = String(sessionId || "").trim();
      if (!key) {
        return current;
      }
      if (saving) {
        return { ...current, [key]: true };
      }
      if (!(key in current)) {
        return current;
      }
      const { [key]: _removed, ...rest } = current;
      return rest;
    });
  }

  function queueSettingsSync(sessionId: string, nextSettings: ChatSettings) {
    const key = String(sessionId || "").trim();
    if (!key) {
      return;
    }
    queuedSettingsBySessionIdRef.current[key] = nextSettings;
    if (inFlightSettingsBySessionIdRef.current[key]) {
      return;
    }

    const flush = () => {
      const queued = queuedSettingsBySessionIdRef.current[key];
      if (!queued) {
        setSettingsSaving(key, false);
        return;
      }
      queuedSettingsBySessionIdRef.current[key] = undefined;
      inFlightSettingsBySessionIdRef.current[key] = true;
      setSettingsSaving(key, true);
      updateChatSettings.mutate(
        {
          sessionId: key,
          settings: queued,
          traceContext: createTraceContext({
            sessionId: key,
            chatId: key,
            route: "/app/chat",
          }),
        },
        {
          onSuccess: (updated) => {
            setDraftSettingsBySessionId((current) => {
              const draft = current[key];
              if (!draft || !settingsEqual(draft, updated.settings)) {
                return current;
              }
              const { [key]: _removed, ...rest } = current;
              return rest;
            });
          },
          onError: () => {
            if (queuedSettingsBySessionIdRef.current[key]) {
              return;
            }
            setDraftSettingsBySessionId((current) => {
              if (!(key in current)) {
                return current;
              }
              const { [key]: _removed, ...rest } = current;
              return rest;
            });
          },
          onSettled: () => {
            inFlightSettingsBySessionIdRef.current[key] = false;
            if (queuedSettingsBySessionIdRef.current[key]) {
              flush();
              return;
            }
            setSettingsSaving(key, false);
          },
        },
      );
    };

    flush();
  }

  function handleSettingsPatch(patch: Partial<ChatSettings>) {
    const key = activeSessionId || "__new__";
    const nextSettings: ChatSettings = {
      response_style: patch.response_style ?? activeResponseStyle,
      detail_level: patch.detail_level ?? activeDetailLevel,
    };
    setDraftSettingsBySessionId((current) => ({
      ...current,
      [key]: nextSettings,
    }));
    if (activeSessionId) {
      queueSettingsSync(activeSessionId, nextSettings);
    }
  }

  function handleResponseStyleChange(nextStyle: ResponseStyle) {
    handleSettingsPatch({ response_style: nextStyle });
  }

  function handleDetailLevelChange(nextLevel: DetailLevel) {
    handleSettingsPatch({ detail_level: nextLevel });
  }

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
      const settingsForNewChat = activeSettings;
      createChat.mutate(
        {
          title: "Новый чат",
          source: "chat_submit",
          traceContext: baseTrace,
        },
        {
          onSuccess: (created) => {
            setDraftSettingsBySessionId((current) => {
              const { __new__: _removed, ...rest } = current;
              return rest;
            });
            if (!settingsEqual(settingsForNewChat, DEFAULT_CHAT_SETTINGS)) {
              updateChatSettings.mutate({
                sessionId: created.session_id,
                settings: settingsForNewChat,
                traceContext: extendTraceContext(baseTrace, {
                  sessionId: created.session_id,
                  chatId: created.session_id,
                }),
              });
            }
            sendMessage.mutate({
              sessionId: created.session_id,
              content,
              responseStyle: settingsForNewChat.response_style,
              detailLevel: settingsForNewChat.detail_level,
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
      responseStyle: activeResponseStyle,
      detailLevel: activeDetailLevel,
      traceContext: baseTrace,
    });
  }

  const isBootstrappingChat = chatsQuery.isLoading && !activeSessionId;
  const isChatBusy = activeSessionPending || (!activeSessionId && createChat.isPending);
  const isLoadingMessages = !!activeSessionId && messagesQuery.isLoading;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      {!helperAreaHidden && (
        <div data-testid="chat-helper-area" className="border-b px-4 py-4 sm:px-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                <h1 className="text-lg font-semibold">
                  {activeSession?.title ?? "Чат"}
                </h1>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Задавайте бизнес-вопрос напрямую. Если сначала нужно увидеть строки,
                поля и структуру данных, откройте справку и перейдите в предпросмотр.
              </p>
            </div>

            <div className="flex w-full shrink-0 flex-col items-stretch gap-3 sm:w-auto sm:items-end">
              <Button
                variant="outline"
                size="sm"
                className="w-full sm:w-auto"
                onClick={() => setHelpOpen((current) => !current)}
              >
                <BookOpenText className="mr-2 h-4 w-4" />
                {helpOpen ? "Скрыть подсказки" : "Как начать"}
              </Button>

              {!sessions.length && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full sm:w-auto"
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

          <div className="mt-3 space-y-3">
            {helpOpen && (
              <ChatHelpDrawer open={helpOpen} onClose={() => setHelpOpen(false)} />
            )}

            {otherPendingCount > 0 && (
              <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
                В других чатах сейчас выполняется {otherPendingCount === 1 ? "1 запрос" : `${otherPendingCount} запроса`}.
                Вы можете продолжить работу в текущем чате независимо от них.
              </div>
            )}

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
      )}

      <div data-testid="chat-messages-scroll" className="min-h-0 flex-1 overflow-y-auto">
        {isBootstrappingChat ? (
          <div className="flex h-full items-center justify-center px-4 sm:px-6">
            <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
              <Bot className="h-4 w-4" />
              Загружаем список чатов и активный диалог...
            </div>
          </div>
        ) : isLoadingMessages ? (
          <div className="flex h-full items-center justify-center px-4 sm:px-6">
            <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
              Загружаем сообщения...
            </div>
          </div>
        ) : messages.length === 0 ? (
          <ChatEmpty />
        ) : (
          <div className="mx-auto flex w-full max-w-4xl flex-col px-3 py-4 sm:px-4">
            {messages.map((message, index) => (
              <ChatMessage
                key={`${message.created_at}-${message.role}-${index}`}
                message={message}
                responseStyle={activeResponseStyle}
              />
            ))}
            {activeSessionPending && <ChatThinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div
        data-testid="chat-composer-shell"
        className="sticky bottom-0 z-20 shrink-0 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85"
      >
        {messages.length === 0 && isChatBusy && (
          <div className="px-4 pb-2 pt-3 sm:px-6">
            <ChatThinking />
          </div>
        )}

        <ChatControlsBar
          chatTitle={activeSession?.title ?? "новый чат"}
          responseStyle={activeResponseStyle}
          detailLevel={activeDetailLevel}
          disabled={false}
          saving={activeSessionSettingsSaving}
          collapsed={settingsCollapsed}
          onToggleCollapsed={() => setSettingsCollapsed((current) => !current)}
          onResponseStyleChange={handleResponseStyleChange}
          onDetailLevelChange={handleDetailLevelChange}
        />

        <ChatInput
          onSend={handleSend}
          disabled={isChatBusy}
          responseStyle={activeResponseStyle}
          detailLevel={activeDetailLevel}
        />
      </div>
    </div>
  );
}
