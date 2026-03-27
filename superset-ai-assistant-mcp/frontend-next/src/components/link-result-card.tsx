"use client";

import { useState } from "react";
import { ExternalLink, Link2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createTraceContext, describeUsefulLink, logFrontendEvent } from "@/lib/observability";

interface LinkResultCardProps {
  title: string;
  href: string;
  route?: string;
}

export function LinkResultCard({
  title,
  href,
  route = "/app/share",
}: LinkResultCardProps) {
  const [copied, setCopied] = useState(false);
  const linkMeta = describeUsefulLink(href);
  const ctaLabel =
    linkMeta.link_kind === "chart"
      ? "Открыть график"
      : linkMeta.link_kind === "dashboard"
        ? "Открыть дашборд"
        : linkMeta.link_kind === "sql_lab"
          ? "Открыть SQL Lab"
          : "Открыть результат";
  const hint =
    linkMeta.link_kind === "chart"
      ? "Полный интерактивный график в Superset."
      : linkMeta.link_kind === "dashboard"
        ? "Дашборд откроется в новой вкладке."
        : linkMeta.link_kind === "sql_lab"
          ? "SQL Lab откроется в новой вкладке."
          : "Результат откроется в новой вкладке.";

  async function handleCopy() {
    const traceContext = createTraceContext({ route });
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
      logFrontendEvent(
        "useful_link_copy",
        {
          title,
          ...describeUsefulLink(href),
        },
        { traceContext },
      );
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
      <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button asChild size="sm">
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            onClick={() =>
              logFrontendEvent(
                "useful_link_open",
                {
                  title,
                  ...describeUsefulLink(href),
                },
                { traceContext: createTraceContext({ route }) },
              )
            }
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            {ctaLabel}
          </a>
        </Button>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? "Скопировано" : "Скопировать ссылку"}
        </Button>
      </div>
    </div>
  );
}
