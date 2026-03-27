"use client";

import { useId, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";
import { ExternalLink, LineChart, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LinkResultCard } from "@/components/link-result-card";
import { ResultTable } from "@/components/result-table";
import type { ChatArtifact } from "@/lib/chats";

interface ChatArtifactProps {
  artifact: ChatArtifact;
}

interface ChartPoint {
  label: string;
  value: number;
  svgX: number;
  svgY: number;
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

function renderAxisLabel(value: unknown) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed) || /^\d{4}-\d{2}-\d{2}T/.test(trimmed)) {
      const parsed = new Date(trimmed);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed.toLocaleDateString("ru-RU", {
          day: "numeric",
          month: "short",
          year:
            parsed.getUTCFullYear() !== new Date().getUTCFullYear()
              ? "numeric"
              : undefined,
        });
      }
    }
    return trimmed;
  }
  return renderValue(value);
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

function ChartTooltip({
  point,
  xPercent,
  yPercent,
}: {
  point: ChartPoint;
  xPercent: number;
  yPercent: number;
}) {
  return (
    <div
      data-testid="chat-chart-tooltip"
      className="pointer-events-none absolute z-10 w-max max-w-[14rem] -translate-x-1/2 rounded-xl border border-slate-200/90 bg-white/95 px-3 py-2 shadow-lg backdrop-blur"
      style={{
        left: `${xPercent}%`,
        top: `${yPercent}%`,
      }}
    >
      <p className="text-[11px] font-medium text-slate-900">{point.label}</p>
      <p className="mt-0.5 text-xs text-slate-600">{renderValue(point.value)}</p>
    </div>
  );
}

function buildChartGeometry(rows: Record<string, unknown>[], xKey: string, yKey: string) {
  const width = 320;
  const height = 184;
  const left = 18;
  const right = 14;
  const top = 18;
  const bottom = 24;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const rawPoints = rows
    .map((row) => {
      const value = Number(row[yKey]);
      if (!Number.isFinite(value)) {
        return null;
      }
      return {
        label: renderAxisLabel(row[xKey]),
        value,
      };
    })
    .filter((item): item is { label: string; value: number } => !!item);

  const values = rawPoints.map((item) => item.value);
  const maxValue = Math.max(...values, 0);
  const minValue = Math.min(...values, 0);
  const valueSpan = maxValue - minValue;
  const safeSpan = valueSpan === 0 ? Math.max(Math.abs(maxValue), 1) : valueSpan;
  const svgPoints: ChartPoint[] = rawPoints.map((point, index) => {
    const ratioX = rawPoints.length <= 1 ? 0.5 : index / Math.max(rawPoints.length - 1, 1);
    const normalizedValue =
      valueSpan === 0 ? 0.5 : (point.value - minValue) / safeSpan;
    return {
      label: point.label,
      value: point.value,
      svgX: left + ratioX * innerWidth,
      svgY: top + (1 - normalizedValue) * innerHeight,
    };
  });

  return {
    width,
    height,
    left,
    right,
    top,
    bottom,
    innerWidth,
    innerHeight,
    minValue,
    maxValue,
    svgPoints,
    baselineY: top + innerHeight,
    gridYs: [0, 0.33, 0.66, 1].map((ratio) => top + ratio * innerHeight),
  };
}

function ChartPreview({ artifact }: ChatArtifactProps) {
  const payload = artifact.payload ?? {};
  const chartType = String(payload.chart_type ?? "bar").trim().toLowerCase();
  const xKey = String(payload.x_key ?? "").trim();
  const yKey = String(payload.y_key ?? "").trim();
  const href = getPayloadHref(payload);
  const linkLabel = getPayloadLinkLabel(payload, "Открыть график");
  const rows = coerceRows(payload);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const gradientId = useId();
  const chart = useMemo(() => buildChartGeometry(rows, xKey, yKey), [rows, xKey, yKey]);

  if (!rows.length || !xKey || !yKey || !chart.svgPoints.length) {
    return null;
  }

  const hoveredPoint =
    hoveredIndex === null ? null : chart.svgPoints[hoveredIndex] ?? null;
  const tooltipX =
    hoveredPoint == null
      ? 50
      : Math.min(Math.max((hoveredPoint.svgX / chart.width) * 100, 14), 86);
  const tooltipY =
    hoveredPoint == null
      ? 10
      : Math.min(Math.max((hoveredPoint.svgY / chart.height) * 100 - 12, 6), 68);

  const commonHeader = (
    <>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <LineChart className="h-4 w-4 text-primary" />
          <p className="text-sm font-medium">{artifact.title || "Preview графика"}</p>
        </div>
        <span className="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
          {chartType === "line" ? "line" : "bar"}
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
    </>
  );

  function handleSurfaceMove(event: ReactMouseEvent<HTMLDivElement>) {
    if (!chart.svgPoints.length) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) {
      return;
    }
    const relativeX = ((event.clientX - rect.left) / rect.width) * chart.width;
    let nearestIndex = 0;
    let nearestDistance = Number.POSITIVE_INFINITY;
    chart.svgPoints.forEach((point, index) => {
      const distance = Math.abs(point.svgX - relativeX);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    });
    setHoveredIndex(nearestIndex);
  }

  if (chartType === "line") {
    const polylinePoints = chart.svgPoints.map((point) => `${point.svgX},${point.svgY}`).join(" ");
    const areaPath = [
      `M ${chart.svgPoints[0]?.svgX ?? chart.left} ${chart.baselineY}`,
      ...chart.svgPoints.map((point) => `L ${point.svgX} ${point.svgY}`),
      `L ${chart.svgPoints[chart.svgPoints.length - 1]?.svgX ?? chart.left} ${chart.baselineY}`,
      "Z",
    ].join(" ");

    return (
      <div
        data-testid="chat-chart-preview"
        data-chart-type="line"
        className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm"
      >
        {commonHeader}
        <div
          data-testid="chat-chart-surface"
          className="relative mt-4 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3"
          onMouseMove={handleSurfaceMove}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          {hoveredPoint && (
            <ChartTooltip point={hoveredPoint} xPercent={tooltipX} yPercent={tooltipY} />
          )}
          <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-44 w-full overflow-visible">
            <defs>
              <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#2563eb" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            {chart.gridYs.map((y, index) => (
              <line
                key={index}
                x1={chart.left}
                y1={y}
                x2={chart.width - chart.right}
                y2={y}
                stroke="rgba(148, 163, 184, 0.28)"
                strokeWidth="1"
              />
            ))}
            <path d={areaPath} fill={`url(#${gradientId})`} />
            <polyline
              fill="none"
              stroke="#2563eb"
              strokeWidth="2.75"
              strokeLinejoin="round"
              strokeLinecap="round"
              points={polylinePoints}
            />
            {chart.svgPoints.map((point, index) => (
              <g key={`${point.label}-${index}`}>
                <circle
                  data-point-index={index}
                  cx={point.svgX}
                  cy={point.svgY}
                  r="8"
                  fill="transparent"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
                <circle
                  cx={point.svgX}
                  cy={point.svgY}
                  r={hoveredIndex === index ? "4.5" : "3.25"}
                  fill="#ffffff"
                  stroke="#2563eb"
                  strokeWidth="2"
                  className="transition-all"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
              </g>
            ))}
          </svg>
          <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-slate-500">
            <span>{chart.svgPoints[0]?.label ?? "—"}</span>
            <span>
              {chart.minValue === chart.maxValue
                ? `Значение: ${renderValue(chart.maxValue)}`
                : `Диапазон: ${renderValue(chart.minValue)} — ${renderValue(chart.maxValue)}`}
            </span>
            <span>{chart.svgPoints[chart.svgPoints.length - 1]?.label ?? "—"}</span>
          </div>
        </div>
        <ArtifactAction href={href} label={linkLabel} />
      </div>
    );
  }

  return (
    <div
      data-testid="chat-chart-preview"
      data-chart-type="bar"
      className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm"
    >
      {commonHeader}
      <div
        data-testid="chat-chart-surface"
        className="relative mt-4 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3"
        onMouseMove={handleSurfaceMove}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        {hoveredPoint && (
          <ChartTooltip point={hoveredPoint} xPercent={tooltipX} yPercent={tooltipY} />
        )}
        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-44 w-full overflow-visible">
          {chart.gridYs.map((y, index) => (
            <line
              key={index}
              x1={chart.left}
              y1={y}
              x2={chart.width - chart.right}
              y2={y}
              stroke="rgba(148, 163, 184, 0.24)"
              strokeWidth="1"
            />
          ))}
          {chart.svgPoints.map((point, index) => {
            const barWidth = Math.max(chart.innerWidth / Math.max(chart.svgPoints.length * 1.9, 2), 10);
            const baseY = chart.baselineY;
            const barHeight = Math.max(baseY - point.svgY, 6);
            const x = point.svgX - barWidth / 2;
            const y = baseY - barHeight;
            return (
              <g key={`${point.label}-${index}`}>
                <rect
                  data-bar-index={index}
                  x={x}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  rx="8"
                  fill={hoveredIndex === index ? "#1d4ed8" : "#3b82f6"}
                  fillOpacity={hoveredIndex === index ? "0.92" : "0.82"}
                  onMouseEnter={() => setHoveredIndex(index)}
                />
                <rect
                  data-chart-hitbox={index}
                  x={x - 6}
                  y={chart.top}
                  width={barWidth + 12}
                  height={chart.innerHeight}
                  fill="transparent"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
              </g>
            );
          })}
        </svg>
        <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-slate-500">
          <span>{chart.svgPoints[0]?.label ?? "—"}</span>
          <span>{`Диапазон: ${renderValue(chart.minValue)} — ${renderValue(chart.maxValue)}`}</span>
          <span>{chart.svgPoints[chart.svgPoints.length - 1]?.label ?? "—"}</span>
        </div>
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
      <div
        data-testid="chat-table-preview"
        className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm"
      >
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
