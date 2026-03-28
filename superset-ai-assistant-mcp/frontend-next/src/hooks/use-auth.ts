"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authApi, type AuthUser } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import {
  extendTraceContext,
  logFrontendEvent,
  type FrontendTraceContext,
} from "@/lib/observability";

const AUTH_KEY = ["auth", "me"] as const;
type AuthMutationVariables = {
  username: string;
  password: string;
  traceContext?: Partial<FrontendTraceContext>;
};

type LogoutVariables = {
  traceContext?: Partial<FrontendTraceContext>;
};

/** Current-user query.  Fires on mount and caches for 5 min. */
export function useAuth() {
  const {
    data: user,
    isLoading,
    error,
  } = useQuery<AuthUser, ApiError>({
    queryKey: AUTH_KEY,
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user && !error,
  };
}

/** Login mutation — on success, refetch /me and navigate to /app. */
export function useLogin() {
  const qc = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (variables: AuthMutationVariables) =>
      authApi.login(
        { username: variables.username, password: variables.password },
        variables.traceContext,
      ),
    onSuccess: (user, variables) => {
      qc.setQueryData(AUTH_KEY, user);
      logFrontendEvent(
        "auth_login_success",
        { role: user.role },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: user.session_id,
            chatId: user.session_id,
            route: "/login",
          }),
        },
      );
      router.push("/app");
    },
  });
}

/** Register mutation — on success, refetch /me and navigate to /app. */
export function useRegister() {
  const qc = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (variables: AuthMutationVariables) =>
      authApi.register(
        { username: variables.username, password: variables.password },
        variables.traceContext,
      ),
    onSuccess: (user, variables) => {
      qc.setQueryData(AUTH_KEY, user);
      logFrontendEvent(
        "auth_register_success",
        { role: user.role },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            sessionId: user.session_id,
            chatId: user.session_id,
            route: "/register",
          }),
        },
      );
      router.push("/app");
    },
  });
}

/** Logout mutation — clears auth cache and navigates to /login. */
export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (variables?: LogoutVariables) => authApi.logout(variables?.traceContext),
    onSuccess: (_data, variables) => {
      logFrontendEvent(
        "auth_logout",
        {},
        { traceContext: extendTraceContext(variables?.traceContext, { route: "/app" }) },
      );
      qc.setQueryData(AUTH_KEY, null);
      qc.invalidateQueries({ queryKey: AUTH_KEY });
      router.push("/login");
    },
  });
}
