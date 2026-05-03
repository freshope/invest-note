"use client";

import { useQuery } from "@tanstack/react-query";
import type { Period } from "@/lib/analysis/period";
import { analysisApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_ANALYSIS_STALE_TIME_MS } from "@/lib/constants/query";

export type { BehaviorData, SuggestionsData } from "@/lib/api-client";

export function useAnalysisData(period: Period) {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: queryKeys.analysisDashboard(period),
    queryFn: () => analysisApi.dashboard(period),
    staleTime: QUERY_ANALYSIS_STALE_TIME_MS,
  });

  return {
    summary: data?.summary ?? null,
    behavior: data?.behavior ?? null,
    suggestionsData: data?.suggestions ?? null,
    missingQuoteTickers: data?.missingQuoteTickers ?? [],
    loading: isPending,
    isError,
    refetch,
  };
}
