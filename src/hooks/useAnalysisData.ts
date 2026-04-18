"use client";

import { useQueries } from "@tanstack/react-query";
import type { Period } from "@/lib/analysis/period";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";
import type { BehaviorProfile, ProfileInputRates } from "@/lib/analysis/profile";
import type { ConcentrationData } from "@/lib/analysis/concentration";
import type { Suggestion } from "@/lib/analysis/rules";

export interface BehaviorData {
  period?: Period;
  profile: BehaviorProfile;
  inputRates: ProfileInputRates;
  holdingPeriodDist: { bucket: string; count: number }[];
  positionSizeDist: { bucket: string; count: number }[];
  concentration: ConcentrationData;
}

export interface SuggestionsData {
  period?: Period;
  suggestions: Suggestion[];
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch failed: ${url}`);
  return res.json();
}

export function useAnalysisData(period: Period) {
  const [summaryQ, behaviorQ, suggestionsQ] = useQueries({
    queries: [
      {
        queryKey: ["analysis", "summary", period],
        queryFn: () => fetchJson<AnalysisSummary>(`/api/analysis/summary?period=${period}`),
      },
      {
        queryKey: ["analysis", "behavior", period],
        queryFn: () => fetchJson<BehaviorData>(`/api/analysis/behavior?period=${period}`),
      },
      {
        queryKey: ["analysis", "suggestions", period],
        queryFn: () => fetchJson<SuggestionsData>(`/api/analysis/suggestions?period=${period}`),
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
