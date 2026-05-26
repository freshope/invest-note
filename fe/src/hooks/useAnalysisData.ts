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
  // staleTime:0 으로 전역 기본 staleTime(30s)에 막혀 캐시를 반환하지 않고 항상 네트워크를
  // 타도록 강제한다 — pull-to-refresh 는 늘 최신.
  const refetch = useCallback(
    () =>
      queryClient.fetchQuery({
        queryKey: queryKeys.analysisDashboard(period),
        queryFn: () => analysisApi.dashboard(period, true),
        staleTime: 0,
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
