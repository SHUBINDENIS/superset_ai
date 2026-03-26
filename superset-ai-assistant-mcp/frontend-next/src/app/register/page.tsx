"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { useAuth, useRegister } from "@/hooks/use-auth";

export default function RegisterPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const register = useRegister();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) router.replace("/app");
  }, [isAuthenticated, router]);

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
