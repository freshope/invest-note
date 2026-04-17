"use client";

import { useState, useEffect, useCallback } from "react";
import { PeriodFilterTabs } from "./PeriodFilterTabs";
import { SummaryCards } from "./SummaryCards";
import { InsightHighlights, seedInsights } from "./InsightHighlights";
import { EmotionBreakdown } from "./EmotionBreakdown";
import { StrategyBreakdown } from "./StrategyBreakdown";
import { ReasoningBreakdown } from "./ReasoningBreakdown";
import { BehaviorRadar } from "./BehaviorRadar";
import { DiversificationPanel } from "./DiversificationPanel";
import { ReviewQualityPanel } from "./ReviewQualityPanel";
import { DrilldownHistograms } from "./DrilldownHistograms";
import { SuggestionList } from "./SuggestionList";
import { AnalysisEmptyState } from "./AnalysisEmptyState";
import type { Period } from "@/lib/analysis/period";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";
import type { BehaviorProfile, ProfileInputRates } from "@/lib/analysis/profile";
import type { ConcentrationData } from "@/lib/analysis/concentration";
import type { Suggestion } from "@/lib/analysis/rules";

interface BehaviorData {
  profile: BehaviorProfile;
  inputRates: ProfileInputRates;
  holdingPeriodDist: { bucket: string; count: number }[];
  positionSizeDist: { bucket: string; count: number }[];
  concentration: ConcentrationData;
}

interface SuggestionsData {
  suggestions: Suggestion[];
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
      <h2 className="text-[13px] font-semibold text-foreground">{title}</h2>
      {children}
    </div>
  );
}

function SkeletonCard({ h = "h-28" }: { h?: string }) {
  return <div className={`rounded-2xl bg-muted/60 ${h} animate-pulse`} />;
}

export function AnalysisDashboard() {
  const [period, setPeriod] = useState<Period>("3m");
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [behavior, setBehavior] = useState<BehaviorData | null>(null);
  const [suggestionsData, setSuggestionsData] = useState<SuggestionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (p: Period) => {
    setLoading(true);
    setError(null);
    try {
      const [summaryRes, behaviorRes, suggestionsRes] = await Promise.all([
        fetch(`/api/analysis/summary?period=${p}`),
        fetch(`/api/analysis/behavior?period=${p}`),
        fetch(`/api/analysis/suggestions?period=${p}`),
      ]);
      if (!summaryRes.ok || !behaviorRes.ok || !suggestionsRes.ok) throw new Error();
      const [s, b, sg] = await Promise.all([summaryRes.json(), behaviorRes.json(), suggestionsRes.json()]);
      setSummary(s);
      setBehavior(b);
      setSuggestionsData(sg);
    } catch {
      setError("분석 데이터를 불러오는 중 오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(period);
  }, [period, fetchData]);

  const isEmpty = summary && summary.totalTrades === 0;

  return (
    <div className="px-5 pt-5 pb-24 space-y-4">
      <PeriodFilterTabs value={period} onChange={setPeriod} />

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
          <SkeletonCard h="h-16" />
          <SkeletonCard h="h-56" />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : isEmpty ? (
        <AnalysisEmptyState hasTrades={false} />
      ) : summary ? (
        <>
          {/* 섹션 1: 핵심 성과 */}
          <SummaryCards summary={summary} />

          {/* 섹션 2: 오늘의 인사이트 — 룰 기반 상위 3개 */}
          {(() => {
            const suggestions = suggestionsData?.suggestions ?? [];
            const top3 = suggestions.slice(0, 3).map((s) => ({
              id: s.id,
              severity: s.severity,
              title: s.title,
              body: s.body,
            }));
            const fallback = top3.length === 0 ? seedInsights(summary) : top3;
            return fallback.length > 0 ? <InsightHighlights insights={fallback} /> : null;
          })()}

          {/* 섹션 3: 투자 성향 프로필 */}
          {behavior && (
            <SectionCard title="투자 성향 프로필">
              <BehaviorRadar profile={behavior.profile} inputRates={behavior.inputRates} />
            </SectionCard>
          )}

          {/* 섹션 4: 감정별 성과 */}
          {summary.byEmotion.length > 0 && (
            <SectionCard title="감정별 성과">
              <EmotionBreakdown data={summary.byEmotion} />
            </SectionCard>
          )}

          {/* 섹션 5: 전략별 성과 */}
          {summary.byStrategy.length > 0 && (
            <SectionCard title="전략별 성과">
              <StrategyBreakdown data={summary.byStrategy} />
            </SectionCard>
          )}

          {/* 섹션 6: 근거 태그별 성과 */}
          {(summary.byTag.length > 0 || summary.missingTagRate > 0 || summary.feelingRate > 0) && (
            <SectionCard title="근거 태그별 성과">
              <ReasoningBreakdown
                data={summary.byTag}
                summary={{ feelingRate: summary.feelingRate, missingTagRate: summary.missingTagRate }}
              />
            </SectionCard>
          )}

          {/* 섹션 7: 분산 / 집중도 */}
          {behavior && (
            <SectionCard title="포트폴리오 분산">
              <DiversificationPanel concentration={behavior.concentration} />
            </SectionCard>
          )}

          {/* 섹션 8: 회고 품질 */}
          {behavior && (
            <SectionCard title="데이터 입력 품질">
              <ReviewQualityPanel
                inputRates={behavior.inputRates}
                reflectionRate={summary.reflectionRate}
                resultInputRate={summary.resultInputRate}
              />
            </SectionCard>
          )}

          {/* 섹션 10: 드릴다운 히스토그램 */}
          {behavior &&
            (behavior.holdingPeriodDist.length > 0 || behavior.positionSizeDist.length > 0) && (
              <SectionCard title="거래 패턴 상세">
                <DrilldownHistograms
                  holdingPeriodDist={behavior.holdingPeriodDist}
                  positionSizeDist={behavior.positionSizeDist}
                />
              </SectionCard>
            )}

          {/* 섹션 9: 방향성 제안 */}
          {suggestionsData && (
            <SectionCard title="투자 방향성 제안">
              <SuggestionList suggestions={suggestionsData.suggestions} />
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
