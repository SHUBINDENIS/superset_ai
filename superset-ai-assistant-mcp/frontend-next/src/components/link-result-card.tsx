"use client";

import { useState } from "react";
import { ExternalLink, Link2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LinkResultCardProps {
  title: string;
  href: string;
}

export function LinkResultCard({ title, href }: LinkResultCardProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2">
        <Link2 className="h-4 w-4 text-primary" />
        <p className="text-sm font-medium">{title}</p>
      </div>
      <p className="mt-2 break-all text-xs text-muted-foreground">{href}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button asChild size="sm">
          <a href={href} target="_blank" rel="noreferrer">
            <ExternalLink className="mr-2 h-4 w-4" />
            Открыть
          </a>
        </Button>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? "Скопировано" : "Скопировать ссылку"}
        </Button>
      </div>
    </div>
  );
}
