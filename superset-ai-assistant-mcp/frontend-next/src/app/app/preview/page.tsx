"use client";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
  type SelectHTMLAttributes,
} from "react";
import { ArrowRight, Eye, RefreshCw, Share2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { VizFlowGuide } from "@/components/viz-flow-guide";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResultTable } from "@/components/result-table";
import {
  buildPreviewTemplateSql,
  PREVIEW_TEMPLATE_LABELS,
  type PreviewTemplate,
} from "@/lib/viz";
import { createTraceContext, logFrontendEvent } from "@/lib/observability";
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
  const { previewState, recommendation } = useVizFlow();

  const [databaseId, setDatabaseId] = useState<number | null>(null);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [previewLimit, setPreviewLimit] = useState<number>(20);
  const [template, setTemplate] = useState<PreviewTemplate>("table_preview");
  const [columnTypeFilter, setColumnTypeFilter] = useState("all");
  const [columnFocus, setColumnFocus] = useState("");
  const [feedback, setFeedback] = useState<string>("");
  const [localError, setLocalError] = useState<string>("");

  const databases = databasesQuery.data?.databases ?? [];
  const allDatasets = datasetsQuery.data?.datasets ?? [];
  const selectedDatabase = useMemo(
    () => databases.find((item) => item.id === databaseId) ?? null,
    [databaseId, databases],
  );

  const datasetCandidates = useMemo(() => {
    if (!databaseId) {
      return [];
    }
    const selectedDatabaseName = String(selectedDatabase?.name || "").trim();
    return allDatasets.filter((item) => {
      if (item.database_id === databaseId) {
        return true;
      }
      if (item.database_id !== null) {
        return false;
      }
      return (
        selectedDatabaseName.length > 0 &&
        String(item.database_name || "").trim() === selectedDatabaseName
      );
    });
  }, [allDatasets, databaseId, selectedDatabase?.name]);

  const selectedDataset = useMemo(
    () => datasetCandidates.find((item) => item.id === datasetId) ?? null,
    [datasetCandidates, datasetId],
  );
  const metadataQuery = useDatasetMetadata(datasetId);
  const metadata = metadataQuery.data ?? null;
  const preview = previewState?.preview ?? null;
  const previewContextLabel =
    previewState?.datasetLabel ||
    selectedDataset?.table_name ||
    "выбранный датасет";
  const previewHasRows = Boolean(preview && preview.rows.length > 0);

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

  function handleRunPreview() {
    clearMessages();
    if (!databaseId) {
      setLocalError("Выберите базу данных для предпросмотра.");
      return;
    }
    if (!selectedDataset) {
      setLocalError("Выберите таблицу/датасет для быстрого просмотра.");
      return;
    }
    let sql = "";
    try {
      sql = buildPreviewTemplateSql({
        dataset: selectedDataset,
        metadata,
        template,
        previewLimit,
      });
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Не удалось подготовить быстрый просмотр.",
      );
      return;
    }
    const traceContext = createTraceContext({ route: "/app/preview" });
    logFrontendEvent(
      "preview_run",
      {
        database_id: databaseId,
        dataset_id: datasetId ?? "",
        preview_limit: previewLimit,
        sql_chars: sql.trim().length,
        source_window: "preview",
      },
      { traceContext },
    );
    previewMutation.mutate({
      database_id: databaseId,
      dataset_id: datasetId,
      schema: selectedDataset.schema || "",
      sql,
      preview_limit: previewLimit,
      datasetLabel: selectedDataset.table_name,
      databaseName: selectedDatabase?.name || "",
      previewTemplate: template,
      traceContext,
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

        <VizFlowGuide
          currentStep="preview"
          hasPreview={!!preview}
          hasRecommendation={!!recommendation}
        />

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
                      {item.name} ({item.backend})
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
                  disabled={!databaseId || datasetCandidates.length === 0}
                >
                  {datasetCandidates.length === 0 && (
                    <option value="">
                      {databaseId
                        ? "Для выбранной базы таблицы не найдены"
                        : "Сначала выберите базу данных"}
                    </option>
                  )}
                  {datasetCandidates.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.table_name}
                    </option>
                  ))}
                </SelectField>
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
              Выберите таблицу/датасет и нажмите «Быстро посмотреть данные».
              Шаблон запроса будет собран автоматически на основе выбранного
              сценария и доступной metadata.
            </div>

            {metadata && (
              <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
                Metadata загружена: колонок {metadata.columns.length}, метрик{" "}
                {metadata.metrics.length}. Это помогает подобрать шаблон и
                объяснить поля после preview.
              </div>
            )}

            {previewState && (
              <div className="rounded-lg border bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
                Текущий контекст шага:{" "}
                <span className="font-medium text-foreground">
                  {previewContextLabel}
                </span>
                {previewState.databaseName ? ` из базы ${previewState.databaseName}` : ""}.
                Если обновите preview, этот же контекст автоматически перейдёт
                в рекомендации и затем в создание виджета.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Запуск просмотра</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
              Кнопка ниже сразу выполняет запрос на основе выбранных базы,
              датасета, шаблона и лимита строк. Дополнительная ручная настройка
              SQL на этом шаге больше не требуется.
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handleRunPreview}
                disabled={previewMutation.isPending || !selectedDataset || !databaseId}
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
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <Button asChild variant="outline">
                <Link href="/app/recommend">Перейти к рекомендациям без preview</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/app/share">Сразу к созданию графика</Link>
              </Button>
            </div>
          </div>
        ) : (
          <>
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="text-base">Следующий логичный шаг</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Preview по <span className="font-medium text-foreground">{previewContextLabel}</span>{" "}
                  выполнен: видно {preview.rows_count} строк и {preview.columns.length} полей.
                  Дальше можно либо подобрать тип графика автоматически, либо сразу
                  создать виджет вручную на том же контексте.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button asChild>
                    <Link href="/app/recommend">
                      <Sparkles className="mr-2 h-4 w-4" />
                      Подобрать тип графика
                    </Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/app/share">
                      <Share2 className="mr-2 h-4 w-4" />
                      Сразу создать виджет
                    </Link>
                  </Button>
                </div>
                {!previewHasRows && (
                  <p className="text-sm text-muted-foreground">
                    Preview выполнился без строк. В этом случае сначала стоит
                    проверить источник или шаблон, а затем переходить к следующему шагу.
                  </p>
                )}
              </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-2">
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

                <div className="flex flex-wrap gap-3 pt-2">
                  <Button asChild>
                    <Link href="/app/recommend">
                      Продолжить к рекомендациям
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/app/share">Открыть создание графика</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
