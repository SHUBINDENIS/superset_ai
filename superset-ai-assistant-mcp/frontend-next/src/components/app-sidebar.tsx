"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Eye,
  Sparkles,
  Share2,
  ScanSearch,
  LogOut,
  User,
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

export function AppSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const logout = useLogout();
  const onChatPage = pathname.startsWith("/app/chat");
  const { data: chatList } = useChats({ enabled: onChatPage });

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-14 shrink-0 items-center border-b px-4">
        <span className="text-sm font-semibold tracking-tight">
          Superset AI
        </span>
      </div>

      {/* Navigation */}
      <nav className="space-y-1 p-2">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Chat sessions — only visible on /app/chat */}
      {onChatPage && (
        <div className="flex-1 overflow-y-auto border-t px-2 py-3">
          <ChatSidebar sessions={chatList?.sessions ?? []} />
        </div>
      )}

      {/* Spacer when not on chat page */}
      {!onChatPage && <div className="flex-1" />}

      {/* User / logout */}
      <div className="shrink-0 border-t p-3">
        <div className="mb-2 flex items-center gap-2 px-1">
          <User className="h-4 w-4 text-muted-foreground" />
          <span className="truncate text-sm text-muted-foreground">
            {user?.username ?? "..."}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2"
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
          {logout.isPending ? "Выход..." : "Выйти"}
        </Button>
      </div>
    </aside>
  );
}
