import { apiFetch } from "./api-client";
import type { FrontendTraceContext } from "./observability";

export interface SchemaScanSummary {
  database_candidates_count: number;
  postgres_candidates_count: number;
  selected_databases_count: number;
  postgres_databases_count: number;
  tables_profiled_count: number;
  relations_detected_count: number;
}

export interface SchemaScanTableColumn {
  column_name?: string;
  data_type?: string;
  is_nullable?: string;
}

export interface SchemaScanProfiledTable {
  schema: string;
  table: string;
  row_count?: number | null;
  column_count?: number;
  columns?: SchemaScanTableColumn[];
  error?: string;
}

export interface SchemaScanRelation {
  source_schema: string;
  source_table: string;
  source_column: string;
  target_schema: string;
  target_table: string;
  target_column: string;
  relation_type?: string;
  confidence?: string;
  constraint_name?: string;
}

export interface SchemaScanDatabaseReport {
  database_id: number;
  database_name: string;
  backend: string;
  schemas: string[];
  tables_profiled: SchemaScanProfiledTable[];
  relations?: {
    foreign_keys?: SchemaScanRelation[];
    heuristic?: SchemaScanRelation[];
  };
  diagnostics?: {
    tables_fetch_errors?: Array<Record<string, unknown>>;
  };
}

export interface SchemaScanReport {
  generated_at?: string;
  superset_base_url?: string;
  scan_config?: Record<string, unknown>;
  database_candidates?: Array<Record<string, unknown>>;
  postgres_databases?: SchemaScanDatabaseReport[];
  summary?: SchemaScanSummary;
}

export interface SchemaScanResult {
  status: string;
  started_at: string;
  finished_at: string;
  report_path: string;
  summary: SchemaScanSummary;
  report: SchemaScanReport;
}

export function buildScanDatabaseRows(report: SchemaScanReport) {
  const rows: Array<Record<string, unknown>> = [];
  const postgresDatabases = report.postgres_databases ?? [];

  for (const database of postgresDatabases) {
    const relations = database.relations ?? {};
    const foreignKeys = relations.foreign_keys ?? [];
    const heuristic = relations.heuristic ?? [];
    const fetchErrors = database.diagnostics?.tables_fetch_errors ?? [];
    const tableProfileErrors = (database.tables_profiled ?? []).filter(
      (table) => Boolean(String(table.error || "").trim()),
    ).length;

    rows.push({
      database_id: database.database_id,
      database_name: database.database_name,
      backend: database.backend,
      schemas: Array.isArray(database.schemas) ? database.schemas.length : 0,
      tables_profiled: Array.isArray(database.tables_profiled)
        ? database.tables_profiled.length
        : 0,
      fk_relations: foreignKeys.length,
      heuristic_relations: heuristic.length,
      table_profile_errors: tableProfileErrors,
      schema_fetch_errors: fetchErrors.length,
    });
  }

  return rows;
}

export function buildScanRelationRows(
  report: SchemaScanReport,
  limit = 120,
) {
  const rows: Array<Record<string, unknown>> = [];
  const postgresDatabases = report.postgres_databases ?? [];

  for (const database of postgresDatabases) {
    const relations = database.relations ?? {};
    const pairs = [
      ["foreign_key", relations.foreign_keys ?? []],
      ["heuristic", relations.heuristic ?? []],
    ] as const;

    for (const [relationType, items] of pairs) {
      for (const relation of items) {
        rows.push({
          database_name: database.database_name,
          relation_type: relationType,
          source: `${relation.source_schema}.${relation.source_table}.${relation.source_column}`,
          target: `${relation.target_schema}.${relation.target_table}.${relation.target_column}`,
          confidence: relation.confidence || "—",
          constraint_name: relation.constraint_name || "—",
        });
        if (rows.length >= limit) {
          return rows;
        }
      }
    }
  }

  return rows;
}

export const scanApi = {
  run: (traceContext?: Partial<FrontendTraceContext>) =>
    apiFetch<SchemaScanResult>("/scan", {
      method: "POST",
      traceContext,
    }),
};
