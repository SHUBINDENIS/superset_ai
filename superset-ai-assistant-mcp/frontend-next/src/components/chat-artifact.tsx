"use client";

import { ExternalLink, LineChart, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LinkResultCard } from "@/components/link-result-card";
import { ResultTable } from "@/components/result-table";
import type { ChatArtifact } from "@/lib/chats";
import { cn } from "@/lib/utils";

interface ChatArtifactProps {
  artifact: ChatArtifact;
}

function renderValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString("ru-RU") : String(value);
  }
  return String(value);
}

function coerceRows(payload: Record<string, unknown>) {
  const rows = payload.rows;
  return Array.isArray(rows)
    ? rows.filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    : [];
}

function coerceColumns(payload: Record<string, unknown>) {
  const raw = payload.columns;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => {
      if (typeof item === "string") {
        return { key: item, label: item };
      }
      if (!item || typeof item !== "object") {
        return null;
      }
      const key = String((item as Record<string, unknown>).key ?? "").trim();
      const label = String(
        (item as Record<string, unknown>).label ??
          (item as Record<string, unknown>).key ??
          "",
      ).trim();
      if (!key) {
        return null;
      }
      return { key, label: label || key };
    })
    .filter((item): item is { key: string; label: string } => !!item);
}

function getPayloadHref(payload: Record<string, unknown>) {
  return String(payload.href ?? "").trim();
}

function getPayloadLinkLabel(
  payload: Record<string, unknown>,
  fallback: string,
) {
  return String(payload.link_label ?? "").trim() || fallback;
}

function ArtifactAction({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  if (!href) {
    return null;
  }
  return (
    <div className="mt-4 flex justify-end">
      <Button asChild size="sm" variant="outline">
        <a href={href} target="_blank" rel="noreferrer">
          <ExternalLink className="mr-2 h-4 w-4" />
          {label}
        </a>
      </Button>
    </div>
  );
}

function ChartPreview({ artifact }: ChatArtifactProps) {
  const payload = artifact.payload ?? {};
  const chartType = String(payload.chart_type ?? "bar").trim().toLowerCase();
  const xKey = String(payload.x_key ?? "").trim();
  const yKey = String(payload.y_key ?? "").trim();
  const href = getPayloadHref(payload);
  const linkLabel = getPayloadLinkLabel(payload, "Открыть график");
  const rows = coerceRows(payload);
  const numericValues = rows
    .map((row) => Number(row[yKey]))
    .filter((value) => Number.isFinite(value));
  const maxValue = Math.max(...numericValues, 0);

  if (!rows.length || !xKey || !yKey) {
    return null;
  }

  if (chartType === "line") {
    const points = rows
      .map((row, index) => {
        const value = Number(row[yKey]);
        if (!Number.isFinite(value)) {
          return null;
        }
        const x = rows.length === 1 ? 0 : (index / Math.max(rows.length - 1, 1)) * 100;
        const y = maxValue > 0 ? 100 - (value / maxValue) * 100 : 100;
        return `${x},${y}`;
      })
      .filter((item): item is string => !!item)
      .join(" ");

    return (
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <LineChart className="h-4 w-4 text-primary" />
            <p className="text-sm font-medium">{artifact.title || "Preview графика"}</p>
          </div>
          <span className="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
            line
          </span>
        </div>
        {artifact.description && (
          <p className="mt-1 text-xs text-muted-foreground">{artifact.description}</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-1">X: {xKey}</span>
          <span className="rounded-full bg-muted px-2 py-1">Y: {yKey}</span>
          <span className="rounded-full bg-muted px-2 py-1">{rows.length} точек</span>
        </div>
        <div className="mt-4 rounded-lg border bg-muted/20 p-3">
          <svg viewBox="0 0 100 100" className="h-40 w-full overflow-visible">
            <line x1="0" y1="100" x2="100" y2="100" stroke="currentColor" className="text-border" strokeWidth="1" />
            <line x1="0" y1="50" x2="100" y2="50" stroke="currentColor" className="text-border/80" strokeWidth="1" />
            <polyline
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              className="text-primary"
              points={points}
            />
          </svg>
          <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
            {rows.slice(0, 6).map((row, index) => (
              <div
                key={`${index}-${String(row[xKey] ?? "")}`}
                className="rounded-md bg-background px-2 py-1"
              >
                <span className="font-medium text-foreground">{renderValue(row[xKey])}</span>
                {" · "}
                {renderValue(row[yKey])}
              </div>
            ))}
          </div>
        </div>
        <ArtifactAction href={href} label={linkLabel} />
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <LineChart className="h-4 w-4 text-primary" />
          <p className="text-sm font-medium">{artifact.title || "Preview графика"}</p>
        </div>
        <span className="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
          bar
        </span>
      </div>
      {artifact.description && (
        <p className="mt-1 text-xs text-muted-foreground">{artifact.description}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        <span className="rounded-full bg-muted px-2 py-1">X: {xKey}</span>
        <span className="rounded-full bg-muted px-2 py-1">Y: {yKey}</span>
        <span className="rounded-full bg-muted px-2 py-1">{rows.length} точек</span>
      </div>
      <div className="mt-4 space-y-3 rounded-lg border bg-muted/20 p-3">
        {rows.slice(0, 8).map((row, index) => {
          const value = Number(row[yKey]);
          const width = maxValue > 0 && Number.isFinite(value) ? (value / maxValue) * 100 : 0;
          return (
            <div key={`${index}-${String(row[xKey] ?? "")}`} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="truncate font-medium text-foreground">{renderValue(row[xKey])}</span>
                <span className="shrink-0 text-muted-foreground">{renderValue(row[yKey])}</span>
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div
                  className={cn("h-2 rounded-full bg-primary transition-all")}
                  style={{ width: `${Math.max(width, value > 0 ? 6 : 0)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <ArtifactAction href={href} label={linkLabel} />
    </div>
  );
}

export function ChatArtifactCard({ artifact }: ChatArtifactProps) {
  const payload = artifact.payload ?? {};

  if (artifact.artifact_type === "link") {
    const href = String(payload.href ?? "").trim();
    if (!href) {
      return null;
    }
    return (
      <LinkResultCard
        title={artifact.title || artifact.description || "Полезная ссылка"}
        href={href}
        route="/app/chat"
      />
    );
  }

  if (artifact.artifact_type === "table_preview") {
    const href = getPayloadHref(payload);
    const linkLabel = getPayloadLinkLabel(payload, "Открыть результат в Superset");
    return (
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Table2 className="h-4 w-4 text-primary" />
            <p className="text-sm font-medium">{artifact.title || "Preview таблицы"}</p>
          </div>
          <span className="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
            table
          </span>
        </div>
        {artifact.description && (
          <p className="mt-1 text-xs text-muted-foreground">{artifact.description}</p>
        )}
        <div className="mt-4">
          <ResultTable
            columns={coerceColumns(payload)}
            rows={coerceRows(payload)}
            emptyText="Нет данных для отображения."
          />
        </div>
        <ArtifactAction href={href} label={linkLabel} />
      </div>
    );
  }

  if (artifact.artifact_type === "chart_preview") {
    return <ChartPreview artifact={artifact} />;
  }

  const href = String(payload.href ?? "").trim();
  if (href) {
    return (
      <div className="rounded-lg border bg-card p-4 text-sm">
        <div className="flex items-center gap-2">
          <ExternalLink className="h-4 w-4 text-primary" />
          <p className="font-medium">{artifact.title || "Результат"}</p>
        </div>
        {artifact.description && (
          <p className="mt-1 text-xs text-muted-foreground">{artifact.description}</p>
        )}
        <div className="mt-3">
          <LinkResultCard
            title={artifact.title || "Открыть результат"}
            href={href}
            route="/app/chat"
          />
        </div>
      </div>
    );
  }

  return null;
}
