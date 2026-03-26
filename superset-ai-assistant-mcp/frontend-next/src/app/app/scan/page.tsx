"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Loader2, ScanSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResultTable } from "@/components/result-table";
import { useSchemaScanMutation } from "@/hooks/use-scan";
import {
  buildScanDatabaseRows,
  buildScanRelationRows,
  type SchemaScanDatabaseReport,
  type SchemaScanResult,
} from "@/lib/scan";

function renderCount(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function buildProfileRows(database: SchemaScanDatabaseReport) {
  return (database.tables_profiled ?? []).map((table) => ({
    schema: table.schema,
    table: table.table,
    row_count: table.row_count ?? "—",
    column_count: table.column_count ?? table.columns?.length ?? 0,
    error: table.error || "—",
  }));
}

export default function ScanPage() {
  const scanMutation = useSchemaScanMutation();
  const [result, setResult] = useState<SchemaScanResult | null>(null);
  const [feedback, setFeedback] = useState("");

  const activeResult = result;
  const report = activeResult?.report;
  const summary = activeResult?.summary;

  const databaseRows = useMemo(
    () => (report ? buildScanDatabaseRows(report) : []),
    [report],
  );
  const relationRows = useMemo(
    () => (report ? buildScanRelationRows(report) : []),
    [report],
  );
  const candidateRows = Array.isArray(report?.database_candidates)
    ? report.database_candidates
    : [];
  const postgresDatabases = Array.isArray(report?.postgres_databases)
    ? report.postgres_databases
    : [];

  function handleReset() {
    scanMutation.reset();
    setResult(null);
    setFeedback("");
  }

  function handleRunScan() {
    setFeedback("");
    setResult(null);
    scanMutation.mutate(undefined, {
      onSuccess: (payload) => {
        setResult(payload);
        setFeedback("Отчёт построен.");
      },
    });
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <ScanSearch className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-semibold">Сканер схем</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Используйте этот раздел, если сначала нужно понять, какие базы,
              схемы и таблицы доступны. Если источник уже понятен, этот шаг
              можно пропустить и перейти в чат или в предпросмотр.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/app/chat">В чат</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/app/preview">В предпросмотр</Link>
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Когда полезно</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Если вы ещё не знаете, где лежат нужные данные, scan поможет
              быстро увидеть доступные PostgreSQL базы, схемы и таблицы.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Когда можно пропустить</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Если бизнес-вопрос уже понятен или таблица уже известна, можно
              сразу идти в чат или открыть «Предпросмотр».
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Что получите</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Отчёт по кандидатам БД, обзор профилированных таблиц и найденных
              связей, пригодный для demo и ручной диагностики.
            </CardContent>
          </Card>
        </div>

        {(feedback || scanMutation.isError) && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              scanMutation.isError
                ? "border-red-200 bg-red-50 text-red-900"
                : "border-emerald-200 bg-emerald-50 text-emerald-900"
            }`}
          >
            {scanMutation.isError
              ? scanMutation.error?.message
              : feedback}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Запуск</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border bg-muted/30 px-4 py-3">
                <p className="text-xs text-muted-foreground">Статус</p>
                <p className="text-lg font-semibold">
                  {scanMutation.isPending
                    ? "Сканирование..."
                    : activeResult?.status === "success"
                      ? "Успешно"
                      : "Готов к запуску"}
                </p>
              </div>
              <div className="rounded-lg border bg-muted/30 px-4 py-3">
                <p className="text-xs text-muted-foreground">Запуск</p>
                <p className="text-sm font-medium">
                  {activeResult?.started_at || "—"}
                </p>
              </div>
              <div className="rounded-lg border bg-muted/30 px-4 py-3">
                <p className="text-xs text-muted-foreground">Завершение</p>
                <p className="text-sm font-medium">
                  {activeResult?.finished_at || "—"}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handleRunScan}
                disabled={scanMutation.isPending}
              >
                {scanMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Сканируем...
                  </>
                ) : activeResult ? (
                  "Перезапустить сканирование"
                ) : (
                  "Запустить сканирование"
                )}
              </Button>
              <Button variant="outline" onClick={handleReset}>
                Сбросить результат
              </Button>
            </div>

            <p className="text-sm text-muted-foreground">
              Текущий backend flow синхронный: страница ждёт, пока сервис
              построит отчёт через built-in MCP.
            </p>
          </CardContent>
        </Card>

        {scanMutation.isPending && (
          <div className="rounded-lg border bg-card px-4 py-8 text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
            <p className="mt-3 text-base font-medium">
              Сканируем метаданные Superset через built-in MCP
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Это полезно, если вы хотите сначала понять, где находятся нужные
              таблицы и как они связаны.
            </p>
          </div>
        )}

        {!activeResult && !scanMutation.isPending ? (
          <div className="rounded-lg border bg-card px-4 py-8 text-center">
            <p className="text-base font-medium">Отчёт ещё не сформирован</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Нажмите «Запустить сканирование», если сначала нужно понять
              структуру источников. Если таблица уже известна, этот шаг можно
              пропустить.
            </p>
          </div>
        ) : null}

        {activeResult && summary ? (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Кандидаты БД</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.database_candidates_count)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">PostgreSQL кандидаты</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.postgres_candidates_count)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Выбранные БД</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.selected_databases_count)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">PostgreSQL БД</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.postgres_databases_count)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Таблиц профилировано</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.tables_profiled_count)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Связей найдено</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {renderCount(summary.relations_detected_count)}
                </CardContent>
              </Card>
            </div>

            {activeResult.report_path ? (
              <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                JSON-отчёт сохранён: {activeResult.report_path}
              </div>
            ) : null}

            {summary.database_candidates_count === 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Superset не вернул ни одной базы данных.
              </div>
            ) : null}

            {summary.database_candidates_count > 0 &&
            summary.selected_databases_count === 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Базы найдены, но ни одна не определилась как PostgreSQL.
                Проверьте `backend_hint` в диагностике ниже.
              </div>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Обзор по базам</CardTitle>
              </CardHeader>
              <CardContent>
                <ResultTable
                  columns={[
                    { key: "database_id", label: "ID" },
                    { key: "database_name", label: "База" },
                    { key: "backend", label: "Backend" },
                    { key: "schemas", label: "Schemas" },
                    { key: "tables_profiled", label: "Tables" },
                    { key: "fk_relations", label: "FK" },
                    { key: "heuristic_relations", label: "Heuristic" },
                    { key: "table_profile_errors", label: "Ошибки профиля" },
                    { key: "schema_fetch_errors", label: "Ошибки schema fetch" },
                  ]}
                  rows={databaseRows}
                  emptyText="В отчёте пока нет профилированных PostgreSQL баз."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Найденные связи</CardTitle>
              </CardHeader>
              <CardContent>
                <ResultTable
                  columns={[
                    { key: "database_name", label: "База" },
                    { key: "relation_type", label: "Тип" },
                    { key: "source", label: "Источник" },
                    { key: "target", label: "Цель" },
                    { key: "confidence", label: "Confidence" },
                    { key: "constraint_name", label: "Constraint" },
                  ]}
                  rows={relationRows}
                  emptyText="Связи не найдены."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Диагностика кандидатов БД</CardTitle>
              </CardHeader>
              <CardContent>
                <ResultTable
                  columns={[
                    { key: "database_id", label: "ID" },
                    { key: "database_name", label: "База" },
                    { key: "backend_hint", label: "backend_hint" },
                    { key: "backend_source", label: "Источник" },
                    { key: "is_postgres", label: "PostgreSQL?" },
                  ]}
                  rows={candidateRows}
                  emptyText="Кандидаты БД отсутствуют."
                />
              </CardContent>
            </Card>

            {postgresDatabases.map((database) => (
              <Card key={`${database.database_id}-${database.database_name}`}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {database.database_name} ({database.backend})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-4">
                    <div className="rounded-lg border bg-muted/30 px-4 py-3">
                      <p className="text-xs text-muted-foreground">Database ID</p>
                      <p className="text-lg font-semibold">{database.database_id}</p>
                    </div>
                    <div className="rounded-lg border bg-muted/30 px-4 py-3">
                      <p className="text-xs text-muted-foreground">Schemas</p>
                      <p className="text-lg font-semibold">
                        {database.schemas?.length ?? 0}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/30 px-4 py-3">
                      <p className="text-xs text-muted-foreground">Tables</p>
                      <p className="text-lg font-semibold">
                        {database.tables_profiled?.length ?? 0}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/30 px-4 py-3">
                      <p className="text-xs text-muted-foreground">Relations</p>
                      <p className="text-lg font-semibold">
                        {(database.relations?.foreign_keys?.length ?? 0) +
                          (database.relations?.heuristic?.length ?? 0)}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-lg border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                    Доступные схемы: {database.schemas?.join(", ") || "—"}
                  </div>

                  <ResultTable
                    columns={[
                      { key: "schema", label: "Schema" },
                      { key: "table", label: "Таблица" },
                      { key: "row_count", label: "Строк" },
                      { key: "column_count", label: "Колонок" },
                      { key: "error", label: "Ошибка" },
                    ]}
                    rows={buildProfileRows(database)}
                    emptyText="Профилированные таблицы не найдены."
                  />

                  <details className="rounded-lg border bg-card px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium">
                      Показать сырой JSON по базе
                    </summary>
                    <pre className="mt-3 overflow-x-auto rounded-md bg-muted p-4 text-xs">
                      {JSON.stringify(database, null, 2)}
                    </pre>
                  </details>
                </CardContent>
              </Card>
            ))}

            <details className="rounded-lg border bg-card px-4 py-3">
              <summary className="cursor-pointer text-sm font-medium">
                Показать сырой JSON всего отчёта
              </summary>
              <pre className="mt-3 overflow-x-auto rounded-md bg-muted p-4 text-xs">
                {JSON.stringify(report, null, 2)}
              </pre>
            </details>
          </>
        ) : null}
      </div>
    </div>
  );
}
