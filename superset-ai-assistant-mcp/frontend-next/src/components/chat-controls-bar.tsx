"use client";

import { ChevronDown, ChevronUp, Settings2 } from "lucide-react";
import type { DetailLevel, ResponseStyle } from "@/lib/chats";
import { Button } from "@/components/ui/button";

interface ChatControlsBarProps {
  chatTitle: string;
  responseStyle: ResponseStyle;
  detailLevel: DetailLevel;
  disabled?: boolean;
  saving?: boolean;
  collapsed?: boolean;
  onToggleCollapsed: () => void;
  onResponseStyleChange: (style: ResponseStyle) => void;
  onDetailLevelChange: (level: DetailLevel) => void;
}

export function ChatControlsBar({
  chatTitle,
  responseStyle,
  detailLevel,
  disabled,
  saving,
  collapsed = false,
  onToggleCollapsed,
  onResponseStyleChange,
  onDetailLevelChange,
}: ChatControlsBarProps) {
  const responseStyleLabel =
    responseStyle === "technical" ? "Технический" : "Бизнес";
  const detailLevelLabel =
    detailLevel === "concise"
      ? "Кратко"
      : detailLevel === "detailed"
        ? "Подробно"
        : "Стандартно";

  return (
    <div className="bg-muted/20 px-3 py-3 sm:px-4">
      <div className="mx-auto max-w-3xl">
        <div
          data-testid="chat-settings-summary"
          className="rounded-xl border bg-card px-3 py-3 shadow-sm"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Settings2 className="h-4 w-4 text-primary" />
                <p className="truncate text-sm font-medium">
                  Настройки: {responseStyleLabel} · {detailLevelLabel}
                </p>
              </div>
              <p className="mt-1 truncate text-xs text-muted-foreground">
                Чат «{chatTitle}». {saving ? "Сохраняем..." : "Параметры применяются к следующим ответам."}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 gap-1.5"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Развернуть настройки" : "Свернуть настройки"}
            >
              {collapsed ? (
                <>
                  Развернуть
                  <ChevronUp className="h-4 w-4" />
                </>
              ) : (
                <>
                  Свернуть
                  <ChevronDown className="h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </div>

        {!collapsed && (
          <div
            data-testid="chat-settings-panel"
            className="mt-3 flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 shadow-sm"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium">Настройки текущего чата</p>
                <p className="text-xs text-muted-foreground">
                  Эти параметры сохраняются для чата «{chatTitle}» и не влияют на другие диалоги.
                </p>
              </div>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {saving ? "Сохраняем..." : "Применяется к следующим ответам"}
              </span>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-sm">
                <span className="font-medium">Режим ответа</span>
                <select
                  value={responseStyle}
                  onChange={(event) =>
                    onResponseStyleChange(
                      event.target.value === "technical" ? "technical" : "business",
                    )
                  }
                  disabled={disabled}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="business">Бизнес</option>
                  <option value="technical">Технический</option>
                </select>
                <span className="text-[11px] text-muted-foreground">
                  Бизнес-режим делает акцент на выводах и интерпретации, технический — на структуре и деталях.
                </span>
              </label>

              <label className="flex flex-col gap-1.5 text-sm">
                <span className="font-medium">Глубина ответа</span>
                <select
                  value={detailLevel}
                  onChange={(event) =>
                    onDetailLevelChange(
                      event.target.value === "concise"
                        ? "concise"
                        : event.target.value === "detailed"
                          ? "detailed"
                          : "standard",
                    )
                  }
                  disabled={disabled}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="concise">Кратко</option>
                  <option value="standard">Стандартно</option>
                  <option value="detailed">Подробно</option>
                </select>
                <span className="text-[11px] text-muted-foreground">
                  Используйте краткий режим для быстрого решения, а подробный — когда нужны допущения и следующий шаг.
                </span>
              </label>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
