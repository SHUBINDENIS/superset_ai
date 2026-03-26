/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * All requests go to `/api/...` which Next.js rewrites proxy to the
 * FastAPI server.  Cookies are included automatically (`credentials:
 * "include"`) so the httpOnly auth cookie flows transparently.
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

export async function apiFetch<T>(
  path: string,
  init?: ApiRequestInit,
): Promise<T> {
  const res = await fetch(`/api${path}`, {
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
