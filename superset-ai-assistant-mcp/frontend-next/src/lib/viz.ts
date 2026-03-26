import { apiFetch } from "./api-client";

export interface DatabaseItem {
  id: number;
  name: string;
  backend: string;
}

export interface DatabaseListResponse {
  databases: DatabaseItem[];
}

export interface DatasetItem {
  id: number;
  table_name: string;
  schema: string;
  database_name: string;
  database_id: number | null;
}

export interface DatasetListResponse {
  datasets: DatasetItem[];
}

export interface DatasetColumn {
  column_name: string;
  verbose_name: string;
  type: string;
}

export interface DatasetMetadata {
  id: number;
  table_name: string;
  schema: string;
  database_id: number | null;
  database_name: string;
  columns: DatasetColumn[];
  metrics: string[];
}

export interface PreviewColumnProfile {
  column: string;
  inferred_type: string;
  unit: string;
  non_null_count: number;
  distinct_count: number;
  sample_value: unknown;
  explanation: string;
}

export interface FieldExplanation {
  column: string;
  explanation: string;
}

export interface PreviewResult {
  dataset_id: number | null;
  database_id: number;
  schema: string;
  sql_executed: string;
  preview_limit: number;
  rows_count: number;
  rows: Array<Record<string, unknown>>;
  columns: PreviewColumnProfile[];
  field_explanations: FieldExplanation[];
}

export interface PreviewRequest {
  database_id: number;
  sql: string;
  schema?: string;
  preview_limit?: number;
  dataset_id?: number | null;
}

export interface RecommendationCandidate {
  viz_type: string;
  score: number;
  reason: string;
}

export interface RecommendationSelectedColumns {
  metric: string;
  dimension: string;
  time: string;
}

export interface RecommendationResult {
  recommended: string;
  candidates: RecommendationCandidate[];
  selected_columns: RecommendationSelectedColumns;
}

export interface RecommendRequest {
  rows: Array<Record<string, unknown>>;
  columns: PreviewColumnProfile[];
  metric_column?: string;
  dimension_column?: string;
  time_column?: string;
}

export interface ShareWidgetRequest {
  dataset_id: number;
  dashboard_title: string;
  slice_name: string;
  viz_type: string;
  metric_column?: string;
  dimension_column?: string;
  time_column?: string;
  row_limit?: number;
  description?: string;
}

export interface ShareWidgetResult {
  dashboard_id: number;
  chart_id: number;
  dashboard_url: string;
  chart_url: string;
  dashboard_link: string;
  chart_link: string;
  params: Record<string, unknown>;
  viz_type: string;
}

export type PreviewTemplate =
  | "table_preview"
  | "count_rows"
  | "top_categories"
  | "daily_trend";

export const PREVIEW_TEMPLATE_LABELS: Record<PreviewTemplate, string> = {
  table_preview: "Первые строки таблицы",
  count_rows: "Сколько всего записей",
  top_categories: "Какие категории встречаются чаще",
  daily_trend: "Как меняются данные по дням",
};

export const COMMON_VIZ_TYPES = [
  "table",
  "line",
  "bar",
  "pie",
  "scatter",
  "area",
] as const;

function quoteIdent(value: string): string {
  const clean = String(value || "").trim();
  if (!clean) {
    return "";
  }
  return `"${clean.replace(/"/g, "\"\"")}"`;
}

function buildTableRef(schemaName: string, tableName: string) {
  const table = quoteIdent(tableName);
  if (!table) {
    return "";
  }
  const schema = quoteIdent(schemaName);
  return schema ? `${schema}.${table}` : table;
}

function classifyMetadataColumn(type: string) {
  const token = String(type || "").toLowerCase();
  if (
    token.includes("date") ||
    token.includes("time") ||
    token.includes("timestamp")
  ) {
    return "temporal";
  }
  if (
    token.includes("int") ||
    token.includes("float") ||
    token.includes("double") ||
    token.includes("decimal") ||
    token.includes("numeric") ||
    token.includes("number")
  ) {
    return "numeric";
  }
  return "categorical";
}

export function collectColumnOptions(
  previewColumns: PreviewColumnProfile[],
  metadataColumns: DatasetColumn[],
) {
  const numeric: string[] = [];
  const temporal: string[] = [];
  const categorical: string[] = [];

  const addUnique = (target: string[], raw: string) => {
    const token = String(raw || "").trim();
    if (!token || target.includes(token)) {
      return;
    }
    target.push(token);
  };

  for (const column of previewColumns) {
    const name = String(column.column || "").trim();
    if (!name) continue;
    if (column.inferred_type === "numeric") addUnique(numeric, name);
    else if (column.inferred_type === "temporal") addUnique(temporal, name);
    else addUnique(categorical, name);
  }

  for (const column of metadataColumns) {
    const name = String(column.column_name || "").trim();
    if (!name) continue;
    const kind = classifyMetadataColumn(column.type);
    if (kind === "numeric") addUnique(numeric, name);
    else if (kind === "temporal") addUnique(temporal, name);
    else addUnique(categorical, name);
  }

  return { numeric, temporal, categorical };
}

export function buildPreviewTemplateSql(params: {
  dataset: DatasetItem;
  metadata: DatasetMetadata | null;
  template: PreviewTemplate;
  previewLimit: number;
}) {
  const { dataset, metadata, template, previewLimit } = params;
  const tableRef = buildTableRef(dataset.schema, dataset.table_name);
  if (!tableRef) {
    throw new Error("Не удалось определить таблицу для SQL-шаблона.");
  }

  if (template === "count_rows") {
    return `SELECT COUNT(*) AS row_count\nFROM ${tableRef}`;
  }

  if (template === "top_categories" || template === "daily_trend") {
    const columns = metadata?.columns ?? [];
    let temporalColumn = "";
    let numericColumn = "";
    let categoricalColumn = "";

    for (const column of columns) {
      const name = String(column.column_name || "").trim();
      const kind = classifyMetadataColumn(column.type);
      if (!name) continue;
      if (!temporalColumn && kind === "temporal") temporalColumn = name;
      if (!numericColumn && kind === "numeric") numericColumn = name;
      if (!categoricalColumn && kind === "categorical") categoricalColumn = name;
    }

    if (template === "top_categories") {
      const targetColumn =
        categoricalColumn ||
        temporalColumn ||
        numericColumn ||
        String(columns[0]?.column_name || "").trim();
      if (!targetColumn) {
        return `SELECT *\nFROM ${tableRef}`;
      }
      const columnRef = quoteIdent(targetColumn);
      const topLimit = Math.max(5, Math.min(previewLimit || 20, 100));
      return (
        `SELECT ${columnRef} AS category, COUNT(*) AS records\n` +
        `FROM ${tableRef}\n` +
        `GROUP BY ${columnRef}\n` +
        `ORDER BY records DESC\n` +
        `LIMIT ${topLimit}`
      );
    }

    if (temporalColumn) {
      const temporalRef = quoteIdent(temporalColumn);
      if (numericColumn) {
        const numericRef = quoteIdent(numericColumn);
        return (
          `SELECT DATE_TRUNC('day', ${temporalRef}) AS day, SUM(${numericRef}) AS total_value\n` +
          `FROM ${tableRef}\n` +
          `GROUP BY day\n` +
          `ORDER BY day DESC`
        );
      }
      return (
        `SELECT DATE_TRUNC('day', ${temporalRef}) AS day, COUNT(*) AS records\n` +
        `FROM ${tableRef}\n` +
        `GROUP BY day\n` +
        `ORDER BY day DESC`
      );
    }
  }

  return `SELECT *\nFROM ${tableRef}`;
}

export const vizApi = {
  listDatabases: () => apiFetch<DatabaseListResponse>("/viz/databases"),

  listDatasets: (limit = 300) =>
    apiFetch<DatasetListResponse>(`/viz/datasets?limit=${encodeURIComponent(limit)}`),

  getDatasetMetadata: (datasetId: number) =>
    apiFetch<DatasetMetadata>(`/viz/datasets/${datasetId}`),

  preview: (payload: PreviewRequest) =>
    apiFetch<PreviewResult>("/viz/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  recommend: (payload: RecommendRequest) =>
    apiFetch<RecommendationResult>("/viz/recommend", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createWidget: (payload: ShareWidgetRequest) =>
    apiFetch<ShareWidgetResult>("/viz/share/widget", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
