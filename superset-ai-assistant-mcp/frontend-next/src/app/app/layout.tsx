"use client";

import { Menu } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { AppSidebar } from "@/components/app-sidebar";
import { ChatUIProvider } from "@/hooks/use-chats";
import { VizFlowProvider } from "@/hooks/use-viz";
import { createTraceContext, logFrontendEvent, routeToWindow } from "@/lib/observability";
import { Button } from "@/components/ui/button";

const DESKTOP_SIDEBAR_STORAGE_KEY = "superset-ai:desktop-sidebar-collapsed";

function getPageTitle(pathname: string) {
  if (pathname.startsWith("/app/chat")) return "Чат";
  if (pathname.startsWith("/app/preview")) return "Предпросмотр";
  if (pathname.startsWith("/app/recommend")) return "Рекомендации";
  if (pathname.startsWith("/app/share")) return "Шеринг";
  if (pathname.startsWith("/app/scan")) return "Сканер схем";
  return "Рабочая область";
}

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
  const [desktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const pageTitle = useMemo(() => getPageTitle(pathname), [pathname]);

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

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const stored = window.localStorage.getItem(DESKTOP_SIDEBAR_STORAGE_KEY);
      setDesktopSidebarCollapsed(stored === "true");
    } catch {
      setDesktopSidebarCollapsed(false);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(
        DESKTOP_SIDEBAR_STORAGE_KEY,
        desktopSidebarCollapsed ? "true" : "false",
      );
    } catch {
      // Sidebar state persistence is non-critical.
    }
  }, [desktopSidebarCollapsed]);

  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [pathname]);

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
        <div className="flex h-[100dvh] overflow-hidden bg-background">
          <AppSidebar
            collapsed={desktopSidebarCollapsed}
            mobileOpen={mobileSidebarOpen}
            onToggleCollapsed={() =>
              setDesktopSidebarCollapsed((current) => !current)
            }
            onMobileOpenChange={setMobileSidebarOpen}
          />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur lg:hidden">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setMobileSidebarOpen(true)}
                aria-label="Открыть навигацию"
              >
                <Menu className="h-4 w-4" />
              </Button>
              <div className="min-w-0">
                <p className="text-sm font-semibold tracking-tight">Superset AI</p>
                <p className="truncate text-xs text-muted-foreground">{pageTitle}</p>
              </div>
            </header>
            <main className="min-h-0 min-w-0 flex-1 overflow-hidden">{children}</main>
          </div>
        </div>
      </VizFlowProvider>
    </ChatUIProvider>
  );
}
