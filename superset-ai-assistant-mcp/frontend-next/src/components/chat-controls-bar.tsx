"use client";

import type { DetailLevel, ResponseStyle } from "@/lib/chats";

interface ChatControlsBarProps {
  chatTitle: string;
  responseStyle: ResponseStyle;
  detailLevel: DetailLevel;
  disabled?: boolean;
  saving?: boolean;
  onResponseStyleChange: (style: ResponseStyle) => void;
  onDetailLevelChange: (level: DetailLevel) => void;
}

export function ChatControlsBar({
  chatTitle,
  responseStyle,
  detailLevel,
  disabled,
  saving,
  onResponseStyleChange,
  onDetailLevelChange,
}: ChatControlsBarProps) {
  return (
    <div className="border-t bg-muted/20 px-4 py-3">
      <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Настройки текущего чата</p>
            <p className="text-xs text-muted-foreground">
              Эти параметры сохраняются для чата «{chatTitle}» и не влияют на другие диалоги.
            </p>
          </div>
          <span className="text-[11px] text-muted-foreground">
            {saving ? "Сохраняем..." : "Сохраняется автоматически"}
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
    </div>
  );
}
