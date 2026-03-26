"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import {
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import {
  type DatabaseListResponse,
  type DatasetListResponse,
  type DatasetMetadata,
  type PreviewRequest,
  type PreviewResult,
  type RecommendationResult,
  type RecommendRequest,
  type ShareWidgetRequest,
  type ShareWidgetResult,
  vizApi,
} from "@/lib/viz";
import {
  extendTraceContext,
  logFrontendEvent,
  type FrontendTraceContext,
} from "@/lib/observability";

interface PreviewFlowState {
  datasetId: number | null;
  databaseId: number | null;
  sql: string;
  preview: PreviewResult | null;
}

interface VizFlowContextValue {
  previewState: PreviewFlowState | null;
  recommendation: RecommendationResult | null;
  setPreviewState: (value: PreviewFlowState | null) => void;
  setRecommendation: (value: RecommendationResult | null) => void;
}

const VizFlowContext = createContext<VizFlowContextValue>({
  previewState: null,
  recommendation: null,
  setPreviewState: () => {},
  setRecommendation: () => {},
});

export function VizFlowProvider({ children }: { children: ReactNode }) {
  const [previewState, setPreviewState] = useState<PreviewFlowState | null>(null);
  const [recommendation, setRecommendation] =
    useState<RecommendationResult | null>(null);

  return (
    <VizFlowContext.Provider
      value={{
        previewState,
        recommendation,
        setPreviewState,
        setRecommendation,
      }}
    >
      {children}
    </VizFlowContext.Provider>
  );
}

export function useVizFlow() {
  return useContext(VizFlowContext);
}

export function useVizDatabases() {
  return useQuery<DatabaseListResponse>({
    queryKey: ["viz", "databases"],
    queryFn: vizApi.listDatabases,
    staleTime: 30_000,
  });
}

export function useVizDatasets(limit = 300) {
  return useQuery<DatasetListResponse>({
    queryKey: ["viz", "datasets", limit],
    queryFn: () => vizApi.listDatasets(limit),
    staleTime: 30_000,
  });
}

export function useDatasetMetadata(datasetId: number | null) {
  return useQuery<DatasetMetadata>({
    queryKey: ["viz", "dataset", datasetId],
    queryFn: () => vizApi.getDatasetMetadata(datasetId!),
    enabled: !!datasetId,
    staleTime: 30_000,
  });
}

export function usePreviewMutation() {
  const { setPreviewState, setRecommendation } = useVizFlow();

  return useMutation({
    mutationFn: (payload: PreviewRequest & { traceContext?: Partial<FrontendTraceContext> }) =>
      vizApi.preview(payload, payload.traceContext),
    onSuccess: (preview, variables) => {
      setPreviewState({
        datasetId: variables.dataset_id ?? null,
        databaseId: variables.database_id,
        sql: preview.sql_executed,
        preview,
      });
      setRecommendation(null);
      logFrontendEvent(
        "preview_run_completed",
        {
          status: "ok",
          database_id: preview.database_id,
          dataset_id: preview.dataset_id ?? "",
          rows_count: preview.rows_count,
          preview_limit: preview.preview_limit,
          column_count: preview.columns.length,
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/preview",
          }),
        },
      );
    },
    onError: (error, variables) => {
      logFrontendEvent(
        "preview_run_completed",
        { status: "error", error_message: error.message },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/preview",
          }),
        },
      );
    },
  });
}

export function useRecommendMutation() {
  const { setRecommendation } = useVizFlow();

  return useMutation({
    mutationFn: (
      payload: RecommendRequest & { traceContext?: Partial<FrontendTraceContext> },
    ) => vizApi.recommend(payload, payload.traceContext),
    onSuccess: (result, variables) => {
      setRecommendation(result);
      logFrontendEvent(
        "viz_recommend_completed",
        {
          status: "ok",
          recommended: result.recommended,
          candidate_count: result.candidates.length,
          row_count: variables.rows.length,
          column_count: variables.columns.length,
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/recommend",
          }),
        },
      );
    },
    onError: (error, variables) => {
      logFrontendEvent(
        "viz_recommend_completed",
        { status: "error", error_message: error.message },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/recommend",
          }),
        },
      );
    },
  });
}

export function useShareWidgetMutation() {
  return useMutation<
    ShareWidgetResult,
    Error,
    ShareWidgetRequest & { traceContext?: Partial<FrontendTraceContext> }
  >({
    mutationFn: (payload) => vizApi.createWidget(payload, payload.traceContext),
    onSuccess: (result, variables) => {
      logFrontendEvent(
        "widget_create_completed",
        {
          status: "ok",
          dataset_id: variables.dataset_id,
          viz_type: result.viz_type,
          dashboard_id: result.dashboard_id,
          chart_id: result.chart_id,
        },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/share",
          }),
        },
      );
    },
    onError: (error, variables) => {
      logFrontendEvent(
        "widget_create_completed",
        { status: "error", error_message: error.message },
        {
          traceContext: extendTraceContext(variables.traceContext, {
            route: "/app/share",
          }),
        },
      );
    },
  });
}
