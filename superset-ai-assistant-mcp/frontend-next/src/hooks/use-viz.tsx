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
    mutationFn: (payload: PreviewRequest) => vizApi.preview(payload),
    onSuccess: (preview, variables) => {
      setPreviewState({
        datasetId: variables.dataset_id ?? null,
        databaseId: variables.database_id,
        sql: preview.sql_executed,
        preview,
      });
      setRecommendation(null);
    },
  });
}

export function useRecommendMutation() {
  const { setRecommendation } = useVizFlow();

  return useMutation({
    mutationFn: (payload: RecommendRequest) => vizApi.recommend(payload),
    onSuccess: (result) => {
      setRecommendation(result);
    },
  });
}

export function useShareWidgetMutation() {
  return useMutation<ShareWidgetResult, Error, ShareWidgetRequest>({
    mutationFn: (payload) => vizApi.createWidget(payload),
  });
}
