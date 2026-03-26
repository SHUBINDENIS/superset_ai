"use client";

import { useMutation } from "@tanstack/react-query";
import {
  scanApi,
  type SchemaScanResult,
} from "@/lib/scan";

export function useSchemaScanMutation() {
  return useMutation<SchemaScanResult, Error, void>({
    mutationFn: () => scanApi.run(),
  });
}
