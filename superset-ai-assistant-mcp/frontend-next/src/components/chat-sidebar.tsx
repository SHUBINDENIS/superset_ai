"use client";

import { useState } from "react";
import { Plus, Pencil, Check, X, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/lib/chats";
import { createTraceContext } from "@/lib/observability";
import {
  useActivateChat,
  useChatUI,
  useCreateChat,
  useClearMessages,
  useDeleteChat,
  useRenameChat,
} from "@/hooks/use-chats";

interface ChatSidebarProps {
  sessions: ChatSession[];
}

export function ChatSidebar({ sessions }: ChatSidebarProps) {
  const { activeSessionId } = useChatUI();
  const activateChat = useActivateChat();
  const createChat = useCreateChat();
  const renameChat = useRenameChat();
  const clearMessages = useClearMessages();
  const deleteChat = useDeleteChat();

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  function startRename(session: ChatSession) {
    setRenamingId(session.session_id);
    setRenameValue(session.title);
  }

  function confirmRename() {
    if (renamingId && renameValue.trim()) {
      renameChat.mutate(
        {
          sessionId: renamingId,
          title: renameValue.trim(),
          traceContext: createTraceContext({
            sessionId: renamingId,
            chatId: renamingId,
            route: "/app/chat",
          }),
        },
        { onSettled: () => setRenamingId(null) },
      );
    }
  }

  function cancelRename() {
    setRenamingId(null);
    setRenameValue("");
  }

  function handleDelete(session: ChatSession) {
    if (!window.confirm(`Удалить чат "${session.title}"?`)) {
      return;
    }
    deleteChat.mutate({
      sessionId: session.session_id,
      traceContext: createTraceContext({
        sessionId: session.session_id,
        chatId: session.session_id,
        route: "/app/chat",
      }),
    });
  }

  function formatTime(iso: string) {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="default"
        size="sm"
        className="w-full justify-start gap-2"
        onClick={() =>
          createChat.mutate({
            title: null,
            source: "sidebar",
            traceContext: createTraceContext({
              sessionId: activeSessionId || undefined,
              chatId: activeSessionId || undefined,
              route: "/app/chat",
            }),
          })
        }
        disabled={createChat.isPending}
      >
        <Plus className="h-3.5 w-3.5" />
        {createChat.isPending ? "Создание..." : "Новый чат"}
      </Button>

      {sessions.length === 0 && (
        <p className="px-1 text-xs text-muted-foreground">
          Чаты пока не найдены.
        </p>
      )}

      <div className="flex flex-col gap-0.5 overflow-y-auto">
        {sessions.map((s) => {
          const isActive = s.session_id === activeSessionId;
          const isRenaming = renamingId === s.session_id;
          const isActivating =
            activateChat.isPending && activateChat.variables?.sessionId === s.session_id;

          return (
            <div
              key={s.session_id}
              className={cn(
                "group flex w-full cursor-pointer flex-col rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                (isRenaming || isActivating) && "cursor-default opacity-80",
              )}
              onClick={() => {
                if (!isRenaming && !isActive && !isActivating) {
                  activateChat.mutate({
                    sessionId: s.session_id,
                    traceContext: createTraceContext({
                      sessionId: s.session_id,
                      chatId: s.session_id,
                      route: "/app/chat",
                    }),
                  });
                }
              }}
            >
              {isRenaming ? (
                <div className="flex items-center gap-1">
                  <Input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmRename();
                      if (e.key === "Escape") cancelRename();
                    }}
                    className="h-6 text-xs"
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      confirmRename();
                    }}
                  >
                    <Check className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      cancelRename();
                    }}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate text-xs font-medium">
                    {s.title}
                  </span>
                  <div className="flex items-center gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        startRename(s);
                      }}
                      title="Переименовать"
                    >
                      <Pencil className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(s);
                      }}
                      title="Удалить чат"
                      disabled={deleteChat.isPending}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}
              {!isRenaming && s.last_message_at && (
                <span className="text-[10px] text-muted-foreground/70 truncate">
                  {isActivating ? "Открытие..." : formatTime(s.last_message_at)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {activeSessionId && (
        <Button
          variant="ghost"
          size="sm"
          className="mt-1 justify-start gap-2 text-xs text-muted-foreground"
          onClick={() =>
            clearMessages.mutate({
              sessionId: activeSessionId,
              traceContext: createTraceContext({
                sessionId: activeSessionId,
                chatId: activeSessionId,
                route: "/app/chat",
              }),
            })
          }
          disabled={clearMessages.isPending}
        >
          <Trash2 className="h-3.5 w-3.5" />
          {clearMessages.isPending ? "Очистка..." : "Очистить чат"}
        </Button>
      )}
    </div>
  );
}
