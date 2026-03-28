"use client";

import { useMutation } from "@tanstack/react-query";
import {
  scanApi,
  type SchemaScanResult,
} from "@/lib/scan";
import {
  extendTraceContext,
  logFrontendEvent,
  type FrontendTraceContext,
} from "@/lib/observability";

export function useSchemaScanMutation() {
  return useMutation<
    SchemaScanResult,
    Error,
    { traceContext?: Partial<FrontendTraceContext> } | undefined
  >({
    mutationFn: (variables) => scanApi.run(variables?.traceContext),
    onSuccess: (result, variables) => {
      logFrontendEvent(
        "schema_scan_completed",
        {
          status: result.status,
          tables_profiled_count: result.summary.tables_profiled_count,
          relations_detected_count: result.summary.relations_detected_count,
          postgres_databases_count: result.summary.postgres_databases_count,
        },
        {
          traceContext: extendTraceContext(variables?.traceContext, {
            route: "/app/scan",
          }),
        },
      );
    },
    onError: (error, variables) => {
      logFrontendEvent(
        "schema_scan_completed",
        { status: "error", error_message: error.message },
        {
          traceContext: extendTraceContext(variables?.traceContext, {
            route: "/app/scan",
          }),
        },
      );
    },
  });
}
