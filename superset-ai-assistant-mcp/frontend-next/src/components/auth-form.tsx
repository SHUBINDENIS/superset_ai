"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";

interface AuthFormProps {
  mode: "login" | "register";
  onSubmit: (data: { username: string; password: string }) => void;
  isPending: boolean;
  error: Error | null;
}

export function AuthForm({ mode, onSubmit, isPending, error }: AuthFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const isLogin = mode === "login";
  const title = isLogin ? "Sign in" : "Create account";
  const description = isLogin
    ? "Enter your credentials to access the assistant."
    : "Register a new account to get started.";
  const submitLabel = isLogin ? "Sign in" : "Create account";
  const altText = isLogin
    ? "Don't have an account?"
    : "Already have an account?";
  const altLink = isLogin ? "/register" : "/login";
  const altLinkText = isLogin ? "Register" : "Sign in";

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({ username, password });
  }

  const errorMessage =
    error instanceof ApiError
      ? error.message
      : error
        ? "Something went wrong. Please try again."
        : null;

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                required
                minLength={isLogin ? 1 : 3}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={isLogin ? "current-password" : "new-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isPending}
              />
            </div>

            {errorMessage && (
              <p className="text-sm text-destructive">{errorMessage}</p>
            )}
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ? "Please wait..." : submitLabel}
            </Button>
            <p className="text-sm text-muted-foreground">
              {altText}{" "}
              <Link href={altLink} className="text-primary underline">
                {altLinkText}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
