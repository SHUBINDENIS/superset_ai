"use client";

const SENSITIVE_KEY_FRAGMENTS = [
  "token",
  "password",
  "secret",
  "authorization",
  "cookie",
  "apikey",
  "api_key",
] as const;

const JWT_RE = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b/g;
const BEARER_RE = /\bbearer\s+[A-Za-z0-9._~+/=-]+\b/gi;
const OPENAI_KEY_RE = /\bsk-[A-Za-z0-9_-]{8,}\b/g;
const KV_SECRET_RE = new RegExp(
  String.raw`\b(${SENSITIVE_KEY_FRAGMENTS.map((item) => item.replace("_", "[_]?")).join("|")})\b\s*[:=]\s*([^\s,;]+)`,
  "gi",
);
const URL_PATTERN = /https?:\/\/[^\s<>)\]]+/g;
let lastNavigationFingerprint = "";
let lastNavigationAt = 0;

export interface FrontendTraceContext {
  traceId: string;
  requestId: string;
  sessionId?: string;
  chatId?: string;
  route?: string;
}

interface FrontendLogEnvelope {
  event: string;
  level: string;
  trace_id: string;
  request_id: string;
  session_id?: string;
  chat_id?: string;
  route?: string;
  metadata: Record<string, unknown>;
}

function randomHex(size = 32) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replace(/-/g, "").slice(0, size);
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`.slice(0, size);
}

export function newTraceId() {
  return randomHex(32);
}

export function newRequestId() {
  return randomHex(32);
}

export function createTraceContext(
  fields: Partial<FrontendTraceContext> = {},
): FrontendTraceContext {
  return {
    traceId: String(fields.traceId || "").trim() || newTraceId(),
    requestId: String(fields.requestId || "").trim() || newRequestId(),
    sessionId: String(fields.sessionId || "").trim() || undefined,
    chatId: String(fields.chatId || "").trim() || undefined,
    route: String(fields.route || "").trim() || undefined,
  };
}

export function extendTraceContext(
  existing: Partial<FrontendTraceContext> | undefined,
  fields: Partial<FrontendTraceContext> = {},
): FrontendTraceContext {
  return createTraceContext({
    traceId: existing?.traceId,
    requestId: existing?.requestId,
    sessionId: fields.sessionId ?? existing?.sessionId,
    chatId: fields.chatId ?? existing?.chatId,
    route: fields.route ?? existing?.route,
  });
}

export function toTraceHeaders(
  traceContext: Partial<FrontendTraceContext> | undefined,
): Record<string, string> {
  if (!traceContext) {
    return {};
  }
  const payload = extendTraceContext(traceContext);
  return {
    "x-trace-id": payload.traceId,
    "x-request-id": payload.requestId,
    "x-session-id": payload.sessionId || "",
    "x-chat-id": payload.chatId || "",
    "x-frontend-source": "nextjs",
  };
}

export function sanitizeText(value: string, maxChars = 200) {
  const raw = String(value || "");
  if (!raw) {
    return "";
  }
  let clean = raw.replace(BEARER_RE, "Bearer [redacted]");
  clean = clean.replace(JWT_RE, "[redacted-jwt]");
  clean = clean.replace(OPENAI_KEY_RE, "[redacted-openai-key]");
  clean = clean.replace(KV_SECRET_RE, "$1=[redacted]");
  if (clean.length > maxChars) {
    return `${clean.slice(0, maxChars - 14).trimEnd()}...[truncated]`;
  }
  return clean;
}

export function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item));
  }
  if (value && typeof value === "object") {
    const next: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      const lowered = key.toLowerCase();
      if (SENSITIVE_KEY_FRAGMENTS.some((fragment) => lowered.includes(fragment))) {
        continue;
      }
      next[key] = sanitizeValue(item);
    }
    return next;
  }
  if (typeof value === "string") {
    return sanitizeText(value);
  }
  return value;
}

export function routeToWindow(route: string) {
  const clean = String(route || "").trim();
  if (!clean) return "";
  if (clean.startsWith("/app/chat")) return "chat";
  if (clean.startsWith("/app/preview")) return "preview";
  if (clean.startsWith("/app/recommend")) return "recommend";
  if (clean.startsWith("/app/share")) return "share";
  if (clean.startsWith("/app/scan")) return "scan";
  if (clean.startsWith("/login")) return "login";
  if (clean.startsWith("/register")) return "register";
  if (clean.startsWith("/app")) return "app";
  return clean;
}

export function extractLinkCount(text: string) {
  return (String(text || "").match(URL_PATTERN) ?? []).length;
}

export function describeUsefulLink(href: string) {
  const raw = String(href || "").trim();
  const fallback = {
    link_kind: "unknown",
    link_host: "",
    link_path: "",
  };
  if (!raw) {
    return fallback;
  }
  try {
    const url = new URL(raw, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    let linkKind = "external";
    if (url.pathname.includes("/explore/") || url.searchParams.has("slice_id")) {
      linkKind = "chart";
    } else if (url.pathname.includes("/dashboard/")) {
      linkKind = "dashboard";
    } else if (url.pathname.includes("/sqllab")) {
      linkKind = "sql_lab";
    } else if (url.origin === (typeof window !== "undefined" ? window.location.origin : url.origin)) {
      linkKind = "internal";
    }
    return {
      link_kind: linkKind,
      link_host: url.host,
      link_path: sanitizeText(url.pathname, 120),
    };
  } catch {
    return fallback;
  }
}

export function logFrontendEvent(
  event: string,
  metadata: Record<string, unknown> = {},
  options: {
    level?: string;
    traceContext?: Partial<FrontendTraceContext>;
  } = {},
): FrontendTraceContext {
  const traceContext = extendTraceContext(options.traceContext, {
    route:
      options.traceContext?.route ||
      (typeof window !== "undefined" ? window.location.pathname : undefined),
  });
  const envelope: FrontendLogEnvelope = {
    event: String(event || "").trim() || "frontend_event",
    level: String(options.level || "INFO").trim().toUpperCase(),
    trace_id: traceContext.traceId,
    request_id: traceContext.requestId,
    session_id: traceContext.sessionId,
    chat_id: traceContext.chatId,
    route: traceContext.route,
    metadata: sanitizeValue(metadata) as Record<string, unknown>,
  };

  if (envelope.event === "window_navigation") {
    const fingerprint = JSON.stringify([
      envelope.event,
      envelope.route,
      envelope.metadata?.["from_route"] || "",
      envelope.metadata?.["to_route"] || "",
    ]);
    const now = Date.now();
    if (fingerprint === lastNavigationFingerprint && now - lastNavigationAt < 1000) {
      return traceContext;
    }
    lastNavigationFingerprint = fingerprint;
    lastNavigationAt = now;
  }

  if (typeof window !== "undefined") {
    void fetch("/api/frontend/logs", {
      method: "POST",
      credentials: "include",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        ...toTraceHeaders(traceContext),
      },
      body: JSON.stringify(envelope),
    }).catch(() => undefined);

    if (process.env.NODE_ENV !== "production") {
      console.info("[frontend-log]", envelope.event, envelope);
    }
  }

  return traceContext;
}
