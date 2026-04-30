"use client";

import { useQuery } from "@tanstack/react-query";
import type { Period } from "@/lib/analysis/period";
import { analysisApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export type { BehaviorData, SuggestionsData } from "@/lib/api-client";

export function useAnalysisData(period: Period) {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: queryKeys.analysisDashboard(period),
    queryFn: () => analysisApi.dashboard(period),
  });

  return {
    summary: data?.summary ?? null,
    behavior: data?.behavior ?? null,
    suggestionsData: data?.suggestions ?? null,
    loading: isPending,
    isError,
    refetch,
  };
}
