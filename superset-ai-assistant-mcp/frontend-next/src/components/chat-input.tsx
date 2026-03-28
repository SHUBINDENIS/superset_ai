"use client";

import { useState, useRef, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DetailLevel, ResponseStyle } from "@/lib/chats";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  responseStyle?: ResponseStyle;
  detailLevel?: DetailLevel;
}

export function ChatInput({
  onSend,
  disabled,
  responseStyle = "business",
  detailLevel = "standard",
}: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    // Reset height
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  return (
    <div className="bg-background px-3 py-3 sm:px-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            autoResize();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Опишите задачу или вопрос по данным…"
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <Button
          size="icon"
          onClick={submit}
          disabled={disabled || !text.trim()}
          title="Отправить"
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
      </div>
      <div className="mx-auto mt-2 flex max-w-3xl flex-col gap-2 text-[11px] text-muted-foreground sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <p>Безопасный режим: задавайте бизнес-вопросы и read-only запросы.</p>
        <p>
          Текущий ответ:{" "}
          <span className="font-medium text-foreground">
            {responseStyle === "technical" ? "Технический" : "Бизнес"}
          </span>
          {" · "}
          <span className="font-medium text-foreground">
            {detailLevel === "concise"
              ? "Кратко"
              : detailLevel === "detailed"
                ? "Подробно"
                : "Стандартно"}
          </span>
        </p>
      </div>
    </div>
  );
}
