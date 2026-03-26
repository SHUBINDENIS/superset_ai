/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * All requests go to `/api/...` which Next.js rewrites proxy to the
 * FastAPI server.  Cookies are included automatically (`credentials:
 * "include"`) so the httpOnly auth cookie flows transparently.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
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
