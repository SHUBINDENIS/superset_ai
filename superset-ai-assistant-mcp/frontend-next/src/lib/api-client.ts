/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * In the browser we prefer a direct FastAPI origin when configured,
 * because long-running chat requests can outlive the Next.js proxy path.
 * Otherwise we fall back to `/api/...` on the same origin.
 */

import type { FrontendTraceContext } from "./observability";
import { toTraceHeaders } from "./observability";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiRequestInit extends RequestInit {
  traceContext?: Partial<FrontendTraceContext>;
}

function resolveApiUrl(path: string): string {
  const cleanPath = `/api${path}`;
  if (typeof window === "undefined") {
    return cleanPath;
  }
  const directBase = (process.env.NEXT_PUBLIC_BROWSER_API_URL || "").trim().replace(/\/+$/, "");
  if (!directBase) {
    return cleanPath;
  }
  return `${directBase}${cleanPath}`;
}

export async function apiFetch<T>(
  path: string,
  init?: ApiRequestInit,
): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...toTraceHeaders(init?.traceContext),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      (body as Record<string, string>).detail || res.statusText,
    );
  }

  return res.json() as Promise<T>;
}
