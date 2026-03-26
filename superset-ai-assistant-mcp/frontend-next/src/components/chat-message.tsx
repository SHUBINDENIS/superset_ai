"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, ShieldAlert, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/lib/chats";

/* ------------------------------------------------------------------ */
/* Content-based message classification                               */
/* ------------------------------------------------------------------ */

const GUARDRAIL_PREFIX =
  "Безопасность: запрос заблокирован намеренно.";
const ERROR_PREFIX = "Ошибка при обработке запроса:";
const URL_PATTERN = /https?:\/\/[^\s<>)\]]+/g;

type MessageKind = "normal" | "blocked" | "error";

function classify(msg: ChatMessageType): MessageKind {
  if (msg.role !== "assistant") return "normal";
  if (msg.finish_reason === "blocked") return "blocked";
  if (msg.finish_reason === "error") return "error";
  if (msg.content.startsWith(GUARDRAIL_PREFIX)) return "blocked";
  if (msg.content.startsWith(ERROR_PREFIX)) return "error";
  return "normal";
}

/** Strip the well-known prefix so the remaining body is cleaner. */
function bodyAfterPrefix(content: string, prefix: string): string {
  if (!content.startsWith(prefix)) {
    return content;
  }
  const rest = content.slice(prefix.length).trim();
  return rest.startsWith("\n") ? rest.slice(1) : rest;
}

function extractLinks(content: string) {
  const matches = content.match(URL_PATTERN) ?? [];
  return Array.from(new Set(matches)).map((url) => {
    let label = "Открыть ссылку";
    if (url.includes("/explore/")) label = "Открыть график";
    else if (url.includes("/dashboard/")) label = "Открыть дашборд";
    else if (url.includes("/sqllab")) label = "Открыть SQL Lab";
    return { url, label };
  });
}

/* ------------------------------------------------------------------ */
/* Component                                                          */
/* ------------------------------------------------------------------ */

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const kind = classify(message);
  const content =
    kind === "blocked"
      ? bodyAfterPrefix(message.content, GUARDRAIL_PREFIX)
      : kind === "error"
        ? bodyAfterPrefix(message.content, ERROR_PREFIX)
        : message.content;
  const links = extractLinks(content);

  return (
    <div
      className={cn("flex gap-3 px-4 py-3", isUser ? "justify-end" : "")}
    >
      {/* Avatar */}
      {!isUser && (
        <div
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
            kind === "blocked"
              ? "bg-amber-100 text-amber-700"
              : kind === "error"
                ? "bg-red-100 text-red-700"
                : "bg-primary/10 text-primary",
          )}
        >
          {kind === "blocked" ? (
            <ShieldAlert className="h-4 w-4" />
          ) : kind === "error" ? (
            <AlertTriangle className="h-4 w-4" />
          ) : (
            <Bot className="h-4 w-4" />
          )}
        </div>
      )}

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-3 py-2 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : kind === "blocked"
              ? "border border-amber-300 bg-amber-50 text-amber-900"
              : kind === "error"
                ? "border border-red-300 bg-red-50 text-red-900"
                : "bg-muted",
        )}
      >
        {/* Blocked banner */}
        {kind === "blocked" && (
          <p className="mb-1 text-xs font-semibold">
            Запрос заблокирован намеренно политикой безопасности
          </p>
        )}

        {/* Error banner */}
        {kind === "error" && (
          <>
            <p className="mb-1 text-xs font-semibold">
              Ассистент не смог обработать запрос
            </p>
          </>
        )}

        {/* Body */}
        <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-li:my-0.5">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>

        {links.length > 0 && (
          <div className="mt-3 border-t pt-2">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide opacity-70">
              Полезные ссылки
            </p>
            <ul className="space-y-1 text-xs">
              {links.map((link) => (
                <li key={link.url}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline underline-offset-2"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Hint for errors */}
        {kind === "error" && (
          <p className="mt-2 text-[11px] opacity-70">
            Попробуйте уточнить формулировку или сократить запрос.
          </p>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Thinking indicator                                                 */
/* ------------------------------------------------------------------ */

export function ChatThinking() {
  return (
    <div className="flex gap-3 px-4 py-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-1.5 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
        <span className="inline-flex gap-1">
          <span className="animate-bounce [animation-delay:0ms]">.</span>
          <span className="animate-bounce [animation-delay:150ms]">.</span>
          <span className="animate-bounce [animation-delay:300ms]">.</span>
        </span>
        <span>Ассистент думает над ответом</span>
      </div>
    </div>
  );
}
