"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Eye,
  Sparkles,
  Share2,
  ScanSearch,
  LogOut,
  Menu,
  User,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth, useLogout } from "@/hooks/use-auth";
import { useChats } from "@/hooks/use-chats";
import { ChatSidebar } from "@/components/chat-sidebar";
import { createTraceContext } from "@/lib/observability";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/app/chat", label: "Чат", icon: MessageSquare },
  { href: "/app/preview", label: "Предпросмотр", icon: Eye },
  { href: "/app/recommend", label: "Рекомендации", icon: Sparkles },
  { href: "/app/share", label: "Шеринг", icon: Share2 },
  { href: "/app/scan", label: "Сканер схем", icon: ScanSearch },
] as const;

interface AppSidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onMobileOpenChange: (open: boolean) => void;
}

export function AppSidebar({
  collapsed,
  mobileOpen,
  onToggleCollapsed,
  onMobileOpenChange,
}: AppSidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const logout = useLogout();
  const onChatPage = pathname.startsWith("/app/chat");
  const { data: chatList } = useChats({ enabled: onChatPage });
  const showExpandedDesktop = !collapsed;
  const showExpandedContent = mobileOpen || showExpandedDesktop;

  return (
    <>
      <button
        type="button"
        className={cn(
          "fixed inset-0 z-40 bg-slate-950/35 transition-opacity lg:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        aria-label="Закрыть навигацию"
        onClick={() => onMobileOpenChange(false)}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[86vw] max-w-72 flex-col border-r bg-card shadow-xl transition-transform duration-200 lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:shadow-none",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          collapsed ? "lg:w-[4.75rem]" : "lg:w-56",
        )}
      >
        <div
          className={cn(
            "flex h-14 shrink-0 items-center border-b",
            collapsed ? "px-2 lg:justify-center" : "px-3 sm:px-4",
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Menu className="h-4 w-4" />
            </div>
            <div className={cn("min-w-0", collapsed && "lg:hidden")}>
              <p className="truncate text-sm font-semibold tracking-tight">Superset AI</p>
              <p className="truncate text-[11px] text-muted-foreground">Навигация и чаты</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => onMobileOpenChange(false)}
              aria-label="Закрыть навигацию"
            >
              <X className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель"}
            >
              {collapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronLeft className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        <nav className="space-y-1 p-2">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                title={label}
                onClick={() => onMobileOpenChange(false)}
                className={cn(
                  "flex items-center rounded-md py-2 text-sm font-medium transition-colors",
                  showExpandedContent ? "gap-3 px-3" : "justify-center px-2 lg:px-0",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className={cn(!showExpandedContent && "lg:hidden")}>{label}</span>
                {!showExpandedContent && <span className="sr-only">{label}</span>}
              </Link>
            );
          })}
        </nav>

        {onChatPage && (
          <div className="flex-1 overflow-y-auto border-t px-2 py-3">
            <ChatSidebar
              sessions={chatList?.sessions ?? []}
              collapsed={!mobileOpen && collapsed}
              onNavigate={() => onMobileOpenChange(false)}
            />
          </div>
        )}

        {!onChatPage && <div className="flex-1" />}

        <div className="shrink-0 border-t p-3">
          <div
            className={cn(
              "mb-2 flex items-center gap-2 px-1",
              !showExpandedContent && "lg:justify-center",
            )}
          >
            <User className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span
              className={cn(
                "truncate text-sm text-muted-foreground",
                !showExpandedContent && "lg:hidden",
              )}
            >
              {user?.username ?? "..."}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            title="Выйти"
            className={cn(
              "gap-2",
              showExpandedContent ? "w-full justify-start" : "w-full justify-center px-0 lg:w-10",
            )}
            onClick={() =>
              logout.mutate({
                traceContext: createTraceContext({
                  sessionId: user?.session_id,
                  chatId: user?.session_id,
                  route: pathname,
                }),
              })
            }
            disabled={logout.isPending}
          >
            <LogOut className="h-4 w-4" />
            <span className={cn(!showExpandedContent && "lg:hidden")}>
              {logout.isPending ? "Выход..." : "Выйти"}
            </span>
          </Button>
        </div>
      </aside>
    </>
  );
}
