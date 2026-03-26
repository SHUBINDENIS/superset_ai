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
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/app/chat", label: "Chat", icon: MessageSquare },
  { href: "/app/preview", label: "Preview", icon: Eye },
  { href: "/app/recommend", label: "Recommend", icon: Sparkles },
  { href: "/app/share", label: "Share", icon: Share2 },
  { href: "/app/scan", label: "Scan", icon: ScanSearch },
] as const;

export function AppSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const logout = useLogout();

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-sm font-semibold tracking-tight">
          Superset AI
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
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

      {/* User / logout */}
      <div className="border-t p-3">
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
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
        >
          <LogOut className="h-4 w-4" />
          {logout.isPending ? "Signing out..." : "Sign out"}
        </Button>
      </div>
    </aside>
  );
}
