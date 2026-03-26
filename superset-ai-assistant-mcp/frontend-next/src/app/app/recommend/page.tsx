"use client";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
  type SelectHTMLAttributes,
} from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResultTable } from "@/components/result-table";
import { useRecommendMutation, useVizFlow } from "@/hooks/use-viz";
import { createTraceContext, logFrontendEvent } from "@/lib/observability";

function SelectField(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    />
  );
}

export default function RecommendPage() {
  const recommendMutation = useRecommendMutation();
  const { previewState, recommendation, setRecommendation } = useVizFlow();
  const preview = previewState?.preview ?? null;
  const previewColumns = preview?.columns ?? [];

  const numericColumns = useMemo(
    () =>
      previewColumns
        .filter((column) => column.inferred_type === "numeric")
        .map((column) => column.column),
    [previewColumns],
  );
  const temporalColumns = useMemo(
    () =>
      previewColumns
        .filter((column) => column.inferred_type === "temporal")
        .map((column) => column.column),
    [previewColumns],
  );
  const categoricalColumns = useMemo(
    () =>
      previewColumns
        .filter((column) =>
          ["text", "boolean"].includes(column.inferred_type),
        )
        .map((column) => column.column),
    [previewColumns],
  );

  const [metricColumn, setMetricColumn] = useState("");
  const [dimensionColumn, setDimensionColumn] = useState("");
  const [timeColumn, setTimeColumn] = useState("");
  const [feedback, setFeedback] = useState("");
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    if (!preview) return;
    const selected = recommendation?.selected_columns;
    if (!metricColumn) {
      setMetricColumn(selected?.metric || numericColumns[0] || "");
    }
    if (!dimensionColumn) {
      setDimensionColumn(selected?.dimension || categoricalColumns[0] || "");
    }
    if (!timeColumn) {
      setTimeColumn(selected?.time || temporalColumns[0] || "");
    }
  }, [
    categoricalColumns,
    dimensionColumn,
    metricColumn,
    numericColumns,
    preview,
    recommendation?.selected_columns,
    temporalColumns,
    timeColumn,
  ]);

  function handleClearRecommendation() {
    setRecommendation(null);
    setFeedback("Рекомендация очищена.");
    setLocalError("");
  }

  function handleRecommend() {
    setFeedback("");
    setLocalError("");
    if (!preview) {
      setLocalError("Сначала выполните предпросмотр с непустым результатом.");
      return;
    }
    const traceContext = createTraceContext({ route: "/app/recommend" });
    logFrontendEvent(
      "viz_recommend_request",
      {
        row_count: preview.rows.length,
        column_count: preview.columns.length,
        metric_selected: Boolean(metricColumn),
        dimension_selected: Boolean(dimensionColumn),
        time_selected: Boolean(timeColumn),
        source_window: "recommend",
      },
      { traceContext },
    );
    recommendMutation.mutate({
      rows: preview.rows,
      columns: preview.columns,
      metric_column: metricColumn,
      dimension_column: dimensionColumn,
      time_column: timeColumn,
      traceContext,
    });
  }

  const result = recommendation;

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-semibold">Рекомендации</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              На основе preview сервис подсказывает тип графика и помогает
              выбрать метрику, группировку и временную ось без ручного
              перебора.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/app/share">Перейти к созданию виджета</Link>
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Строк</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {preview?.rows.length ?? 0}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Числовых полей</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {numericColumns.length}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Временных полей</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {temporalColumns.length}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Категориальных полей</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {categoricalColumns.length}
            </CardContent>
          </Card>
        </div>

        {(feedback || localError || recommendMutation.isError) && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              localError || recommendMutation.isError
                ? "border-red-200 bg-red-50 text-red-900"
                : "border-emerald-200 bg-emerald-50 text-emerald-900"
            }`}
          >
            {localError || recommendMutation.error?.message || feedback}
          </div>
        )}

        {!preview ? (
          <div className="rounded-lg border bg-card px-4 py-8 text-center">
            <p className="text-base font-medium">Нет данных для рекомендации</p>
            <p className="mt-2 text-sm text-muted-foreground">
              В новом frontend этот шаг опирается на preview context. Сначала
              выполните предпросмотр, если хотите проверить поля и значения
              перед выбором графика.
            </p>
            <div className="mt-4">
              <Button asChild>
                <Link href="/app/preview">Открыть предпросмотр</Link>
              </Button>
            </div>
          </div>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Параметры рекомендации</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Метрика</label>
                    <SelectField
                      value={metricColumn}
                      onChange={(event) => setMetricColumn(event.target.value)}
                    >
                      <option value="">Авто</option>
                      {numericColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Группировка</label>
                    <SelectField
                      value={dimensionColumn}
                      onChange={(event) => setDimensionColumn(event.target.value)}
                    >
                      <option value="">Авто</option>
                      {categoricalColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
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
                      <option value="">Авто</option>
                      {temporalColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                </div>

                <p className="text-sm text-muted-foreground">
                  Если поля не выбраны, сервис попробует подобрать их
                  автоматически. Это удобно, когда вы знаете бизнес-вопрос, но
                  не хотите вручную настраивать оси.
                </p>

                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={handleRecommend}
                    disabled={recommendMutation.isPending}
                  >
                    {recommendMutation.isPending
                      ? "Подбираем..."
                      : "Подобрать тип графика"}
                  </Button>
                  <Button variant="outline" onClick={handleClearRecommendation}>
                    Сбросить рекомендацию
                  </Button>
                </div>
              </CardContent>
            </Card>

            {!result ? (
              <div className="rounded-lg border bg-card px-4 py-8 text-center">
                <p className="text-base font-medium">
                  Рекомендация ещё не построена
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Нажмите «Подобрать тип графика», чтобы получить быстрый
                  ориентир перед созданием виджета.
                </p>
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Рекомендуемый тип</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.recommended}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Метрика</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.selected_columns.metric || "—"}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Группировка</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.selected_columns.dimension || "—"}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Временное поле</CardTitle>
                    </CardHeader>
                    <CardContent className="text-2xl font-semibold">
                      {result.selected_columns.time || "—"}
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Кандидаты</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResultTable
                      columns={[
                        { key: "viz_type", label: "Тип" },
                        { key: "score", label: "Score" },
                        { key: "reason", label: "Почему подходит" },
                      ]}
                      rows={result.candidates.map((item) => ({
                        viz_type: item.viz_type,
                        score: item.score,
                        reason: item.reason,
                      }))}
                    />
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
