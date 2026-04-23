"use client";

import { useQueries } from "@tanstack/react-query";
import type { Period } from "@/lib/analysis/period";
import { analysisApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export type { BehaviorData, SuggestionsData } from "@/lib/api-client";

export function useAnalysisData(period: Period) {
  const [summaryQ, behaviorQ, suggestionsQ] = useQueries({
    queries: [
      {
        queryKey: queryKeys.analysisSummary(period),
        queryFn: () => analysisApi.summary(period),
      },
      {
        queryKey: queryKeys.analysisBehavior(period),
        queryFn: () => analysisApi.behavior(period),
      },
      {
        queryKey: queryKeys.analysisSuggestions(period),
        queryFn: () => analysisApi.suggestions(period),
      },
    ],
  });

  const loading = summaryQ.isPending || behaviorQ.isPending || suggestionsQ.isPending;
  const error = summaryQ.isError || behaviorQ.isError || suggestionsQ.isError
    ? "분석 데이터를 불러오는 중 오류가 발생했습니다"
    : null;

  return {
    summary: summaryQ.data ?? null,
    behavior: behaviorQ.data ?? null,
    suggestionsData: suggestionsQ.data ?? null,
    loading,
    error,
  };
}
