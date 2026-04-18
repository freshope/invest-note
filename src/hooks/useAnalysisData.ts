"use client";

import { useState, useEffect, useCallback } from "react";
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

export function useAnalysisData(period: Period) {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [behavior, setBehavior] = useState<BehaviorData | null>(null);
  const [suggestionsData, setSuggestionsData] = useState<SuggestionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (p: Period, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [summaryRes, behaviorRes, suggestionsRes] = await Promise.all([
        fetch(`/api/analysis/summary?period=${p}`, { signal }),
        fetch(`/api/analysis/behavior?period=${p}`, { signal }),
        fetch(`/api/analysis/suggestions?period=${p}`, { signal }),
      ]);

      if (signal.aborted) return;
      if (!summaryRes.ok) throw new Error("summary");

      const [s, b, sg] = await Promise.all([
        summaryRes.json(),
        behaviorRes.ok ? behaviorRes.json() : Promise.resolve(null),
        suggestionsRes.ok ? suggestionsRes.json() : Promise.resolve(null),
      ]);
      setSummary(s);
      setBehavior(b);
      setSuggestionsData(sg);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError("분석 데이터를 불러오는 중 오류가 발생했습니다");
      setSummary(null);
      setBehavior(null);
      setSuggestionsData(null);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchData(period, controller.signal);
    return () => controller.abort();
  }, [period, fetchData]);

  return { summary, behavior, suggestionsData, loading, error };
}
