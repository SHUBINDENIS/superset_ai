"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { useAuth, useLogin } from "@/hooks/use-auth";
import { createTraceContext, logFrontendEvent } from "@/lib/observability";

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const login = useLogin();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) router.replace("/app");
  }, [isAuthenticated, router]);

  useEffect(() => {
    logFrontendEvent(
      "window_navigation",
      { from_window: "", to_window: "login", from_route: "", to_route: "/login" },
      { traceContext: createTraceContext({ route: "/login" }) },
    );
  }, []);

  if (isLoading || isAuthenticated) return null;

  return (
    <AuthForm
      mode="login"
      onSubmit={login.mutate}
      isPending={login.isPending}
      error={login.error}
    />
  );
}
