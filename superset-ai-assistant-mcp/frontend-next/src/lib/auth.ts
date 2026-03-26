/**
 * Auth API functions backed by the FastAPI auth endpoints.
 *
 * Shapes match the Pydantic DTOs in `api/schemas.py`.
 */

import { apiFetch } from "./api-client";
import type { FrontendTraceContext } from "./observability";

export interface AuthUser {
  username: string;
  role: string;
  session_id: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
}

export const authApi = {
  /** Validate the current cookie and return the authenticated user. */
  me: () => apiFetch<AuthUser>("/auth/me"),

  login: (data: LoginRequest, traceContext?: Partial<FrontendTraceContext>) =>
    apiFetch<AuthUser>("/auth/login", {
      method: "POST",
      traceContext,
      body: JSON.stringify(data),
    }),

  register: (data: RegisterRequest, traceContext?: Partial<FrontendTraceContext>) =>
    apiFetch<AuthUser>("/auth/register", {
      method: "POST",
      traceContext,
      body: JSON.stringify(data),
    }),

  logout: (traceContext?: Partial<FrontendTraceContext>) =>
    apiFetch<{ message: string }>("/auth/logout", {
      method: "POST",
      traceContext,
    }),
};
