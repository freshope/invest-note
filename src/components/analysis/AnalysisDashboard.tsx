"use client";

import { useState, useEffect, useCallback } from "react";
import { PeriodFilterTabs } from "./PeriodFilterTabs";
import { SummaryCards } from "./SummaryCards";
import { InsightHighlights, seedInsights } from "./InsightHighlights";
import { EmotionBreakdown } from "./EmotionBreakdown";
import { StrategyBreakdown } from "./StrategyBreakdown";
import { ReasoningBreakdown } from "./ReasoningBreakdown";
import { AnalysisEmptyState } from "./AnalysisEmptyState";
import type { Period } from "@/lib/analysis/period";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
      <h2 className="text-[13px] font-semibold text-foreground">{title}</h2>
      {children}
    </div>
  );
}

function SkeletonCard() {
  return <div className="rounded-2xl bg-muted/60 h-28 animate-pulse" />;
}

export function AnalysisDashboard() {
  const [period, setPeriod] = useState<Period>("3m");
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async (p: Period) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/analysis/summary?period=${p}`);
      if (!res.ok) throw new Error("데이터를 불러오지 못했습니다");
      const data = await res.json();
      setSummary(data);
    } catch {
      setError("분석 데이터를 불러오는 중 오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary(period);
  }, [period, fetchSummary]);

  const handlePeriodChange = (p: Period) => {
    setPeriod(p);
  };

  const isEmpty = summary && summary.totalTrades === 0;

  return (
    <div className="px-5 pt-5 pb-24 space-y-4">
      <PeriodFilterTabs value={period} onChange={handlePeriodChange} />

      {error && (
        <div className="rounded-2xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 p-4 text-[13px] text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : isEmpty ? (
        <AnalysisEmptyState hasTrades={false} />
      ) : summary ? (
        <>
          <SummaryCards summary={summary} />

          {(() => {
            const insights = seedInsights(summary);
            return insights.length > 0 ? <InsightHighlights insights={insights} /> : null;
          })()}

          {summary.byEmotion.length > 0 && (
            <SectionCard title="감정별 성과">
              <EmotionBreakdown data={summary.byEmotion} />
            </SectionCard>
          )}

          {summary.byStrategy.length > 0 && (
            <SectionCard title="전략별 성과">
              <StrategyBreakdown data={summary.byStrategy} />
            </SectionCard>
          )}

          {(summary.byTag.length > 0 || summary.missingTagRate > 0 || summary.feelingRate > 0) && (
            <SectionCard title="근거 태그별 성과">
              <ReasoningBreakdown
                data={summary.byTag}
                summary={{ feelingRate: summary.feelingRate, missingTagRate: summary.missingTagRate }}
              />
            </SectionCard>
          )}

          {summary.sellTrades === 0 && (
            <AnalysisEmptyState hasTrades={summary.totalTrades > 0} hasSells={false} />
          )}
        </>
      ) : null}
    </div>
  );
}
