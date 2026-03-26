"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { AppSidebar } from "@/components/app-sidebar";
import { ChatUIProvider } from "@/hooks/use-chats";
import { VizFlowProvider } from "@/hooks/use-viz";
import { createTraceContext, logFrontendEvent, routeToWindow } from "@/lib/observability";

/**
 * Protected layout for `/app/*` routes.
 *
 * Redirects to /login when the auth cookie is missing or expired.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const previousPathRef = useRef("");

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!pathname || isLoading || !isAuthenticated) {
      return;
    }
    const previousPath = previousPathRef.current;
    logFrontendEvent(
      "window_navigation",
      {
        from_window: routeToWindow(previousPath),
        to_window: routeToWindow(pathname),
        from_route: previousPath,
        to_route: pathname,
      },
      {
        traceContext: createTraceContext({
          sessionId: user?.session_id,
          chatId: user?.session_id,
          route: pathname,
        }),
      },
    );
    previousPathRef.current = pathname;
  }, [isAuthenticated, isLoading, pathname, user?.session_id]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <ChatUIProvider>
      <VizFlowProvider>
        <div className="flex h-screen overflow-hidden">
          <AppSidebar />
          <main className="flex-1 overflow-hidden">{children}</main>
        </div>
      </VizFlowProvider>
    </ChatUIProvider>
  );
}
