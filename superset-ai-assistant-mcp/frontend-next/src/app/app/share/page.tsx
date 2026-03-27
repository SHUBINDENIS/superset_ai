"use client";

import Link from "next/link";
import {
  useEffect,
  useState,
  type SelectHTMLAttributes,
} from "react";
import { ArrowRight, Share2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { VizFlowGuide } from "@/components/viz-flow-guide";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LinkResultCard } from "@/components/link-result-card";
import {
  collectColumnOptions,
  COMMON_VIZ_TYPES,
  type ShareWidgetResult,
} from "@/lib/viz";
import { createTraceContext, logFrontendEvent } from "@/lib/observability";
import {
  useDatasetMetadata,
  useShareWidgetMutation,
  useVizDatasets,
  useVizFlow,
} from "@/hooks/use-viz";

const ROW_LIMITS = [100, 500, 1000, 5000, 10000] as const;

function compactLabel(value: string, fallback: string) {
  const clean = String(value || "").trim();
  return clean || fallback;
}

function buildDashboardTitle(sourceLabel: string) {
  return compactLabel(`Дашборд: ${sourceLabel}`, "AI Dashboard");
}

function buildSliceTitle(params: {
  vizType: string;
  metricColumn: string;
  dimensionColumn: string;
  sourceLabel: string;
}) {
  const { vizType, metricColumn, dimensionColumn, sourceLabel } = params;
  if (metricColumn && dimensionColumn) {
    return compactLabel(`${vizType}: ${metricColumn} по ${dimensionColumn}`, "AI Widget");
  }
  if (metricColumn) {
    return compactLabel(`${vizType}: ${metricColumn}`, "AI Widget");
  }
  return compactLabel(`${vizType}: ${sourceLabel}`, "AI Widget");
}

function SelectField(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    />
  );
}

export default function SharePage() {
  const datasetsQuery = useVizDatasets(300);
  const shareMutation = useShareWidgetMutation();
  const { previewState, recommendation } = useVizFlow();
  const previewColumns = previewState?.preview?.columns ?? [];
  const sourceLabel = previewState?.datasetLabel || "выбранный датасет";
  const hasPreviewContext = !!previewState?.preview;
  const hasRecommendation = !!recommendation;

  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [dashboardTitle, setDashboardTitle] = useState("AI Dashboard");
  const [sliceName, setSliceName] = useState("AI Widget");
  const [vizType, setVizType] = useState("table");
  const [metricColumn, setMetricColumn] = useState("");
  const [dimensionColumn, setDimensionColumn] = useState("");
  const [timeColumn, setTimeColumn] = useState("");
  const [rowLimit, setRowLimit] = useState(1000);
  const [description, setDescription] = useState("");
  const [feedback, setFeedback] = useState("");
  const [localError, setLocalError] = useState("");
  const [result, setResult] = useState<ShareWidgetResult | null>(null);
  const [dashboardTitleTouched, setDashboardTitleTouched] = useState(false);
  const [sliceNameTouched, setSliceNameTouched] = useState(false);
  const [descriptionTouched, setDescriptionTouched] = useState(false);

  const datasets = datasetsQuery.data?.datasets ?? [];
  const metadataQuery = useDatasetMetadata(datasetId);
  const metadata = metadataQuery.data ?? null;

  useEffect(() => {
    if (!datasets.length) return;
    const availableIds = datasets.map((item) => item.id);
    if (datasetId && availableIds.includes(datasetId)) return;
    const preferred = previewState?.datasetId;
    const nextId =
      preferred && availableIds.includes(preferred) ? preferred : datasets[0].id;
    setDatasetId(nextId);
  }, [datasetId, datasets, previewState?.datasetId]);

  useEffect(() => {
    if (recommendation?.recommended && !vizType) {
      setVizType(recommendation.recommended);
    }
  }, [recommendation?.recommended, vizType]);

  useEffect(() => {
    if (recommendation?.recommended) {
      setVizType(recommendation.recommended);
    }
    if (recommendation?.selected_columns.metric) {
      setMetricColumn(recommendation.selected_columns.metric);
    }
    if (recommendation?.selected_columns.dimension) {
      setDimensionColumn(recommendation.selected_columns.dimension);
    }
    if (recommendation?.selected_columns.time) {
      setTimeColumn(recommendation.selected_columns.time);
    }
  }, [recommendation]);

  useEffect(() => {
    if (!dashboardTitleTouched && hasPreviewContext) {
      setDashboardTitle(buildDashboardTitle(sourceLabel));
    }
  }, [dashboardTitleTouched, hasPreviewContext, sourceLabel]);

  useEffect(() => {
    if (!sliceNameTouched) {
      setSliceName(
        buildSliceTitle({
          vizType: recommendation?.recommended || vizType,
          metricColumn: recommendation?.selected_columns.metric || metricColumn,
          dimensionColumn:
            recommendation?.selected_columns.dimension || dimensionColumn,
          sourceLabel,
        }),
      );
    }
  }, [
    dimensionColumn,
    metricColumn,
    recommendation?.recommended,
    recommendation?.selected_columns.dimension,
    recommendation?.selected_columns.metric,
    sliceNameTouched,
    sourceLabel,
    vizType,
  ]);

  useEffect(() => {
    if (!descriptionTouched && !description) {
      if (hasRecommendation) {
        setDescription(
          `Виджет создан по данным ${sourceLabel}. Рекомендованный тип: ${recommendation?.recommended || vizType}.`,
        );
        return;
      }
      if (hasPreviewContext) {
        setDescription(
          `Виджет создан по данным ${sourceLabel} на основе предпросмотра и выбранных полей.`,
        );
      }
    }
  }, [
    description,
    descriptionTouched,
    hasPreviewContext,
    hasRecommendation,
    recommendation?.recommended,
    sourceLabel,
    vizType,
  ]);

  const groupedColumns = collectColumnOptions(previewColumns, metadata?.columns ?? []);

  function clearMessages() {
    setFeedback("");
    setLocalError("");
  }

  async function handleRefreshDatasets() {
    clearMessages();
    await datasetsQuery.refetch();
    setFeedback("Список датасетов обновлён.");
  }

  function handleCreateWidget() {
    clearMessages();
    if (!datasetId) {
      setLocalError("Выберите датасет Superset для создания графика.");
      return;
    }
    const traceContext = createTraceContext({ route: "/app/share" });
    logFrontendEvent(
      "widget_create",
      {
        dataset_id: datasetId,
        viz_type: vizType,
        row_limit: rowLimit,
        dashboard_title_chars: dashboardTitle.trim().length,
        slice_name_chars: sliceName.trim().length,
        description_chars: description.trim().length,
        source_window: "share",
      },
      { traceContext },
    );
    shareMutation.mutate(
      {
        dataset_id: datasetId,
        dashboard_title: dashboardTitle,
        slice_name: sliceName,
        viz_type: vizType,
        metric_column: metricColumn,
        dimension_column: dimensionColumn,
        time_column: timeColumn,
        row_limit: rowLimit,
        description,
        traceContext,
      },
      {
        onSuccess: (payload) => {
          setResult(payload);
          setFeedback("Виджет создан и привязан к дашборду.");
        },
      },
    );
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Share2 className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-semibold">Шеринг</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Финальный шаг: создайте график и дашборд через существующий
              backend flow и сразу получите полезные ссылки для Superset.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/app/recommend">Вернуться к рекомендациям</Link>
          </Button>
        </div>

        <VizFlowGuide
          currentStep="share"
          hasPreview={hasPreviewContext}
          hasRecommendation={hasRecommendation}
        />

        <Card className="border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle className="text-base">Контекст текущего шага</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {hasRecommendation ? (
              <>
                <p>
                  Контекст из preview и рекомендаций уже перенесён. Датасет,
                  тип графика и ключевые поля предзаполнены настолько, насколько
                  это безопасно по текущему flow state.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/recommend">
                      <Sparkles className="mr-2 h-4 w-4" />
                      Вернуться к рекомендации
                    </Link>
                  </Button>
                </div>
              </>
            ) : hasPreviewContext ? (
              <>
                <p>
                  Preview по <span className="font-medium text-foreground">{sourceLabel}</span>{" "}
                  уже есть, поэтому датасет и список полей можно взять из текущего контекста.
                  Если хотите, чтобы тип графика тоже был предложен автоматически,
                  сначала откройте рекомендации.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/recommend">
                      <Sparkles className="mr-2 h-4 w-4" />
                      Сначала подобрать тип графика
                    </Link>
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p>
                  Эту страницу можно использовать и вручную, но сейчас у неё нет
                  контекста из preview или рекомендаций. Поэтому поля и тип графика
                  не предзаполнены.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/preview">Сначала посмотреть данные</Link>
                  </Button>
                  <Button asChild variant="ghost" size="sm">
                    <Link href="/app/recommend">Или сразу к рекомендациям</Link>
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Датасетов</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {datasets.length}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Metadata-колонок</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {metadata?.columns.length ?? 0}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Рекоменд. тип</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {recommendation?.recommended || "—"}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Preview-колонок</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {previewColumns.length}
            </CardContent>
          </Card>
        </div>

        {(feedback || localError || shareMutation.isError) && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              localError || shareMutation.isError
                ? "border-red-200 bg-red-50 text-red-900"
                : "border-emerald-200 bg-emerald-50 text-emerald-900"
            }`}
          >
            {localError || shareMutation.error?.message || feedback}
          </div>
        )}

        {!datasets.length ? (
          <div className="rounded-lg border bg-card px-4 py-8 text-center">
            <p className="text-base font-medium">Список датасетов пуст</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Нажмите «Обновить датасеты», чтобы загрузить доступные источники.
            </p>
            <div className="mt-4">
              <Button onClick={handleRefreshDatasets}>Обновить датасеты</Button>
            </div>
          </div>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Основные настройки</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="outline"
                    onClick={handleRefreshDatasets}
                    disabled={datasetsQuery.isFetching}
                  >
                    Обновить датасеты
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setResult(null)}
                  >
                    Сбросить результат
                  </Button>
                  <Button
                    onClick={handleCreateWidget}
                    disabled={shareMutation.isPending}
                  >
                    {shareMutation.isPending ? "Создаём..." : "Создать виджет"}
                  </Button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Датасет Superset</label>
                    <SelectField
                      value={datasetId ?? ""}
                      onChange={(event) =>
                        setDatasetId(Number(event.target.value) || null)
                      }
                    >
                      {datasets.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.id}: {item.schema ? `${item.schema}.` : ""}
                          {item.table_name}
                          {item.database_name ? ` (${item.database_name})` : ""}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Тип графика</label>
                    <SelectField
                      value={vizType}
                      onChange={(event) => setVizType(event.target.value)}
                    >
                      {COMMON_VIZ_TYPES.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Название дашборда</label>
                    <Input
                      value={dashboardTitle}
                      onChange={(event) => {
                        setDashboardTitleTouched(true);
                        setDashboardTitle(event.target.value);
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Название виджета</label>
                    <Input
                      value={sliceName}
                      onChange={(event) => {
                        setSliceNameTouched(true);
                        setSliceName(event.target.value);
                      }}
                    />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Метрика</label>
                    <SelectField
                      value={metricColumn}
                      onChange={(event) => setMetricColumn(event.target.value)}
                    >
                      <option value="">Не выбрано</option>
                      {groupedColumns.numeric.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Измерение</label>
                    <SelectField
                      value={dimensionColumn}
                      onChange={(event) => setDimensionColumn(event.target.value)}
                    >
                      <option value="">Не выбрано</option>
                      {groupedColumns.categorical.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Временное поле</label>
                    <SelectField
                      value={timeColumn}
                      onChange={(event) => setTimeColumn(event.target.value)}
                    >
                      <option value="">Не выбрано</option>
                      {groupedColumns.temporal.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Ограничение строк</label>
                    <SelectField
                      value={rowLimit}
                      onChange={(event) => setRowLimit(Number(event.target.value))}
                    >
                      {ROW_LIMITS.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    Описание виджета (опционально)
                  </label>
                  <textarea
                    value={description}
                    onChange={(event) => {
                      setDescriptionTouched(true);
                      setDescription(event.target.value);
                    }}
                    rows={4}
                    className="min-h-[96px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                </div>

                <p className="text-sm text-muted-foreground">
                  Если вы пришли сюда после «Рекомендаций», тип графика и поля
                  уже могут быть предзаполнены автоматически. Если же задача
                  уже понятна, этот шаг можно пройти и без recommendation page.
                </p>
              </CardContent>
            </Card>

            {!result ? (
              <div className="rounded-lg border bg-card px-4 py-8 text-center">
                <p className="text-base font-medium">Виджет ещё не создан</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Заполните основные параметры и нажмите «Создать виджет». Если
                  пока непонятно, какой график нужен, вернитесь в
                  «Рекомендации».
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-3">
                  <Button asChild variant="outline">
                    <Link href="/app/recommend">
                      Вернуться к рекомендации
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Dashboard ID</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.dashboard_id}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Chart ID</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.chart_id}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Тип графика</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.viz_type}
                    </CardContent>
                  </Card>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <LinkResultCard
                    title="Ссылка на дашборд"
                    href={result.dashboard_link}
                  />
                  <LinkResultCard
                    title="Ссылка на график"
                    href={result.chart_link}
                  />
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Параметры chart</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="overflow-x-auto rounded-md bg-muted p-4 text-xs">
                      {JSON.stringify(result.params, null, 2)}
                    </pre>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Button asChild>
                        <Link href={result.dashboard_link} target="_blank">
                          Открыть дашборд
                        </Link>
                      </Button>
                      <Button asChild variant="outline">
                        <Link href={result.chart_link} target="_blank">
                          Открыть график
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
