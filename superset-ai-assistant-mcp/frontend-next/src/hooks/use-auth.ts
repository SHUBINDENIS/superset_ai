"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authApi, type AuthUser } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";

const AUTH_KEY = ["auth", "me"] as const;

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
    mutationFn: authApi.login,
    onSuccess: (user) => {
      qc.setQueryData(AUTH_KEY, user);
      router.push("/app");
    },
  });
}

/** Register mutation — on success, refetch /me and navigate to /app. */
export function useRegister() {
  const qc = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.register,
    onSuccess: (user) => {
      qc.setQueryData(AUTH_KEY, user);
      router.push("/app");
    },
  });
}

/** Logout mutation — clears auth cache and navigates to /login. */
export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      qc.setQueryData(AUTH_KEY, null);
      qc.invalidateQueries({ queryKey: AUTH_KEY });
      router.push("/login");
    },
  });
}
