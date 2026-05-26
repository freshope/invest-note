"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { Period } from "@/lib/analysis/period";
import { analysisApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_ANALYSIS_STALE_TIME_MS } from "@/lib/constants/query";

export type { BehaviorData, SuggestionsData } from "@/lib/api-client";

export function useAnalysisData(period: Period) {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.analysisDashboard(period),
    queryFn: () => analysisApi.dashboard(period),
    staleTime: QUERY_ANALYSIS_STALE_TIME_MS,
  });

  // pull-to-refresh / 에러 재시도: refresh=1 로 새 시세를 받아 같은 캐시 키에 덮어쓴다.
  const refetch = useCallback(
    () =>
      queryClient.fetchQuery({
        queryKey: queryKeys.analysisDashboard(period),
        queryFn: () => analysisApi.dashboard(period, true),
      }),
    [queryClient, period]
  );

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
