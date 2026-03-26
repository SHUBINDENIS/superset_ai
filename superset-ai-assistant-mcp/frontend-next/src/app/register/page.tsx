"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { useAuth, useRegister } from "@/hooks/use-auth";
import { createTraceContext, logFrontendEvent } from "@/lib/observability";

export default function RegisterPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const register = useRegister();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) router.replace("/app");
  }, [isAuthenticated, router]);

  useEffect(() => {
    logFrontendEvent(
      "window_navigation",
      { from_window: "", to_window: "register", from_route: "", to_route: "/register" },
      { traceContext: createTraceContext({ route: "/register" }) },
    );
  }, []);

  if (isLoading || isAuthenticated) return null;

  return (
    <AuthForm
      mode="register"
      onSubmit={register.mutate}
      isPending={register.isPending}
      error={register.error}
    />
  );
}
