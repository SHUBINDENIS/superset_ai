"use client";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
  type SelectHTMLAttributes,
} from "react";
import { Eye, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ResultTable } from "@/components/result-table";
import {
  buildPreviewTemplateSql,
  PREVIEW_TEMPLATE_LABELS,
  type PreviewTemplate,
} from "@/lib/viz";
import {
  useDatasetMetadata,
  usePreviewMutation,
  useVizDatabases,
  useVizDatasets,
  useVizFlow,
} from "@/hooks/use-viz";

const PREVIEW_LIMITS = [10, 20, 50, 100, 200] as const;
const COLUMN_TYPE_FILTERS = [
  { value: "all", label: "Все типы" },
  { value: "numeric", label: "Числовые" },
  { value: "temporal", label: "Временные" },
  { value: "text", label: "Текстовые" },
  { value: "boolean", label: "Логические" },
] as const;

function SelectField(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    />
  );
}

export default function PreviewPage() {
  const databasesQuery = useVizDatabases();
  const datasetsQuery = useVizDatasets(300);
  const previewMutation = usePreviewMutation();
  const { previewState } = useVizFlow();

  const [databaseId, setDatabaseId] = useState<number | null>(null);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [schema, setSchema] = useState("");
  const [previewLimit, setPreviewLimit] = useState<number>(20);
  const [template, setTemplate] = useState<PreviewTemplate>("table_preview");
  const [sql, setSql] = useState("");
  const [columnTypeFilter, setColumnTypeFilter] = useState("all");
  const [columnFocus, setColumnFocus] = useState("");
  const [feedback, setFeedback] = useState<string>("");
  const [localError, setLocalError] = useState<string>("");

  const databases = databasesQuery.data?.databases ?? [];
  const allDatasets = datasetsQuery.data?.datasets ?? [];

  const datasetCandidates = useMemo(() => {
    if (!databaseId) {
      return allDatasets;
    }
    const filtered = allDatasets.filter(
      (item) => item.database_id === null || item.database_id === databaseId,
    );
    return filtered.length ? filtered : allDatasets;
  }, [allDatasets, databaseId]);

  const selectedDataset = useMemo(
    () => datasetCandidates.find((item) => item.id === datasetId) ?? null,
    [datasetCandidates, datasetId],
  );
  const metadataQuery = useDatasetMetadata(datasetId);
  const metadata = metadataQuery.data ?? null;
  const preview = previewState?.preview ?? null;

  useEffect(() => {
    if (!databases.length) return;
    const availableIds = databases.map((item) => item.id);
    if (databaseId && availableIds.includes(databaseId)) return;
    const preferred = previewState?.databaseId;
    const nextId =
      preferred && availableIds.includes(preferred) ? preferred : databases[0].id;
    setDatabaseId(nextId);
  }, [databaseId, databases, previewState?.databaseId]);

  useEffect(() => {
    if (!datasetCandidates.length) {
      if (datasetId !== null) setDatasetId(null);
      return;
    }
    const availableIds = datasetCandidates.map((item) => item.id);
    if (datasetId && availableIds.includes(datasetId)) return;
    const preferred = previewState?.datasetId;
    const nextId =
      preferred && availableIds.includes(preferred)
        ? preferred
        : datasetCandidates[0].id;
    setDatasetId(nextId);
  }, [datasetCandidates, datasetId, previewState?.datasetId]);

  useEffect(() => {
    if (selectedDataset?.schema && !schema) {
      setSchema(selectedDataset.schema);
    }
  }, [schema, selectedDataset?.schema]);

  useEffect(() => {
    if (previewState?.sql && !sql) {
      setSql(previewState.sql);
    }
  }, [previewState?.sql, sql]);

  const previewColumns = preview?.columns ?? [];
  const filteredPreviewColumns = previewColumns.filter((column) => {
    if (columnTypeFilter === "all") return true;
    return column.inferred_type === columnTypeFilter;
  });
  const selectedColumn =
    filteredPreviewColumns.find((column) => column.column === columnFocus) ?? null;

  function clearMessages() {
    setFeedback("");
    setLocalError("");
  }

  async function handleRefreshSources() {
    clearMessages();
    await Promise.all([databasesQuery.refetch(), datasetsQuery.refetch()]);
    setFeedback("Источники обновлены.");
  }

  function handleApplyTemplate() {
    clearMessages();
    if (!selectedDataset) {
      setLocalError("Выберите таблицу/датасет, чтобы подготовить быстрый просмотр.");
      return;
    }
    try {
      const nextSql = buildPreviewTemplateSql({
        dataset: selectedDataset,
        metadata,
        template,
        previewLimit,
      });
      setSql(nextSql);
      setFeedback("Основа для быстрого просмотра подготовлена.");
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Не удалось подготовить шаблон.",
      );
    }
  }

  function handleRunPreview() {
    clearMessages();
    if (!databaseId) {
      setLocalError("Выберите базу данных для предпросмотра.");
      return;
    }
    if (!sql.trim()) {
      setLocalError("Подготовьте основу для просмотра или вставьте SQL.");
      return;
    }
    previewMutation.mutate({
      database_id: databaseId,
      dataset_id: datasetId,
      schema,
      sql,
      preview_limit: previewLimit,
    });
  }

  const rowColumns = useMemo(() => {
    const firstRow = preview?.rows?.[0];
    if (!firstRow) return [];
    return Object.keys(firstRow).map((key) => ({ key, label: key }));
  }, [preview?.rows]);

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-semibold">Предпросмотр</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Быстро посмотрите строки и поймите поля. Этот шаг полезен, если
              хочется проверить данные перед рекомендацией или созданием
              графика, но он не обязателен для бизнес-вопроса в чате.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/app/chat">Вернуться в чат</Link>
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. Быстрый взгляд</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Посмотрите несколько строк, чтобы понять, что источник выбран
              правильно.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">2. Понять поля</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Посмотрите объяснения колонок, чтобы выбрать метрику, дату и
              категорию без ручного SQL-анализа.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">3. Можно пропустить</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Если вопрос уже понятен, можно сразу идти в чат или в создание
              графика.
            </CardContent>
          </Card>
        </div>

        {(feedback || localError || previewMutation.isError) && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              localError || previewMutation.isError
                ? "border-red-200 bg-red-50 text-red-900"
                : "border-emerald-200 bg-emerald-50 text-emerald-900"
            }`}
          >
            {localError ||
              previewMutation.error?.message ||
              feedback}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Источник данных</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">База данных</label>
                <SelectField
                  value={databaseId ?? ""}
                  onChange={(event) =>
                    setDatabaseId(Number(event.target.value) || null)
                  }
                >
                  {databases.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}: {item.name} ({item.backend})
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Таблица/датасет для быстрого просмотра
                </label>
                <SelectField
                  value={datasetId ?? ""}
                  onChange={(event) =>
                    setDatasetId(Number(event.target.value) || null)
                  }
                >
                  {datasetCandidates.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}: {item.schema ? `${item.schema}.` : ""}
                      {item.table_name}
                      {item.database_name ? ` (${item.database_name})` : ""}
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Schema</label>
                <Input
                  value={schema}
                  onChange={(event) => setSchema(event.target.value)}
                  placeholder="public"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Что хотите быстро проверить
                </label>
                <SelectField
                  value={template}
                  onChange={(event) =>
                    setTemplate(event.target.value as PreviewTemplate)
                  }
                >
                  {Object.entries(PREVIEW_TEMPLATE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Сколько строк показать</label>
                <SelectField
                  value={previewLimit}
                  onChange={(event) => setPreviewLimit(Number(event.target.value))}
                >
                  {PREVIEW_LIMITS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="flex items-end">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleRefreshSources}
                  disabled={databasesQuery.isFetching || datasetsQuery.isFetching}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Обновить источники
                </Button>
              </div>
            </div>

            <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
              Не хотите думать про SQL? Выберите таблицу/датасет и нажмите
              «Подготовить быстрый просмотр». Если dataset metadata уже
              загрузилась, шаблон возьмёт подходящие поля автоматически.
            </div>

            {metadata && (
              <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
                Metadata загружена: колонок {metadata.columns.length}, метрик{" "}
                {metadata.metrics.length}. Это помогает подобрать шаблон и
                объяснить поля после preview.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Запрос и запуск</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              value={sql}
              onChange={(event) => setSql(event.target.value)}
              rows={8}
              className="min-h-[180px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder="Выберите таблицу выше и подготовьте быстрый просмотр или вставьте свой SQL."
            />
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={handleApplyTemplate}
                disabled={!selectedDataset || metadataQuery.isLoading}
              >
                Подготовить быстрый просмотр
              </Button>
              <Button
                onClick={handleRunPreview}
                disabled={previewMutation.isPending}
              >
                {previewMutation.isPending
                  ? "Готовим просмотр..."
                  : "Быстро посмотреть данные"}
              </Button>
              <Button asChild variant="ghost">
                <Link href="/app/recommend">Перейти к рекомендациям</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {!preview ? (
          <div className="rounded-lg border bg-card px-4 py-8 text-center">
            <p className="text-base font-medium">Быстрый просмотр пока не запущен</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Выберите источник и нажмите «Быстро посмотреть данные», если
              хотите проверить поля и примеры значений. Если это не нужно,
              можно пропустить шаг и вернуться в чат с бизнес-вопросом.
            </p>
          </div>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Database ID</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {preview.database_id}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Schema</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {preview.schema || "—"}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Строк в выборке</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {preview.rows_count}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Лимит preview</CardTitle>
                </CardHeader>
                <CardContent className="text-2xl font-semibold">
                  {preview.preview_limit}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Что видно в данных</CardTitle>
              </CardHeader>
              <CardContent>
                <ResultTable
                  columns={rowColumns}
                  rows={preview.rows}
                  emptyText="Запрос выполнился, но вернул 0 строк."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Понять поля</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Фильтр по типу поля</label>
                    <SelectField
                      value={columnTypeFilter}
                      onChange={(event) => setColumnTypeFilter(event.target.value)}
                    >
                      {COLUMN_TYPE_FILTERS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Поле для подробного объяснения
                    </label>
                    <SelectField
                      value={columnFocus}
                      onChange={(event) => setColumnFocus(event.target.value)}
                    >
                      <option value="">Выберите поле</option>
                      {filteredPreviewColumns.map((item) => (
                        <option key={item.column} value={item.column}>
                          {item.column}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                </div>

                <ResultTable
                  columns={[
                    { key: "column", label: "Поле" },
                    { key: "type", label: "Тип" },
                    { key: "unit", label: "Единица" },
                    { key: "distinct", label: "Distinct" },
                    { key: "sample", label: "Пример" },
                    { key: "explanation", label: "Объяснение" },
                  ]}
                  rows={filteredPreviewColumns.map((item) => ({
                    column: item.column,
                    type: item.inferred_type,
                    unit: item.unit || "—",
                    distinct: item.distinct_count,
                    sample: item.sample_value,
                    explanation: item.explanation,
                  }))}
                  emptyText="Колонки для выбранного фильтра не найдены."
                />

                {selectedColumn && (
                  <div className="rounded-lg border bg-muted/30 px-4 py-3">
                    <div className="grid gap-4 md:grid-cols-4">
                      <div>
                        <p className="text-xs text-muted-foreground">Поле</p>
                        <p className="text-sm font-medium">{selectedColumn.column}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Тип</p>
                        <p className="text-sm font-medium">
                          {selectedColumn.inferred_type}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Distinct</p>
                        <p className="text-sm font-medium">
                          {selectedColumn.distinct_count}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Единица</p>
                        <p className="text-sm font-medium">
                          {selectedColumn.unit || "—"}
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {selectedColumn.explanation}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
