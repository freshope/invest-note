"use client";

import { useState } from "react";
import { PeriodFilterTabs } from "./PeriodFilterTabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { SummaryCards } from "./SummaryCards";
import { EmotionBreakdown } from "./EmotionBreakdown";
import { StrategyBreakdown } from "./StrategyBreakdown";
import { StrategyAdherencePanel } from "./StrategyAdherencePanel";
import { ReasoningBreakdown } from "./ReasoningBreakdown";
import { BehaviorRadar } from "./BehaviorRadar";
import { DiversificationPanel } from "./DiversificationPanel";
import { ReviewQualityPanel } from "./ReviewQualityPanel";
import { DrilldownHistograms } from "./DrilldownHistograms";
import { SuggestionList } from "./SuggestionList";
import { AnalysisEmptyState } from "./AnalysisEmptyState";
import { DEFAULT_ANALYSIS_PERIOD, type Period } from "@/lib/analysis/period";
import { useAnalysisData } from "@/hooks/useAnalysisData";
import { ErrorState } from "@/components/shared/ErrorState";
import { MissingQuoteBadge } from "@/components/shared/MissingQuoteBadge";
import { PullToRefresh } from "@/components/shared/PullToRefresh";

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
  const [period, setPeriod] = useState<Period>(DEFAULT_ANALYSIS_PERIOD);
  const { summary, behavior, suggestionsData, missingQuoteTickers, loading, isError, refetch } = useAnalysisData(period);

  const isEmpty = summary && summary.totalTrades === 0;
  const isEmptyPeriod = !!isEmpty && period !== "all";

  if (!loading && isError) {
    return (
      <PullToRefresh onRefresh={refetch}>
        <>
          <PageHeader title="분석" />
          <ErrorState onRetry={refetch} />
        </>
      </PullToRefresh>
    );
  }

  return (
    <PullToRefresh onRefresh={refetch}>
      <PageHeader
        title="분석"
        actions={loading ? undefined : <PeriodFilterTabs value={period} onChange={setPeriod} compact />}
      />
      <div className="px-5 pt-2 pb-24 space-y-4">
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
          <AnalysisEmptyState hasTrades={isEmptyPeriod} hasSells={isEmptyPeriod} />
        ) : summary ? (
          <>
            <MissingQuoteBadge tickers={missingQuoteTickers} />

            {/* 섹션 1: 핵심 성과 */}
            <SummaryCards summary={summary} />

            {/* 섹션 2: 투자 방향성 제안 */}
            {suggestionsData && <SuggestionList suggestions={suggestionsData.suggestions} />}

            {/* 섹션 3: 투자 행동 프로필 */}
            {behavior && (
              <SectionCard title="투자 행동 프로필">
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

            {(summary.byStrategyAdherence.length > 0 || summary.strategyAdherenceRate > 0) && (
              <SectionCard title="전략 준수 분석">
                <StrategyAdherencePanel
                  rate={summary.strategyAdherenceRate}
                  data={summary.byStrategyAdherence}
                />
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

            {/* 섹션 9: 드릴다운 히스토그램 */}
            {behavior &&
              (behavior.holdingPeriodDist.length > 0 || behavior.positionSizeDist.length > 0) && (
                <SectionCard title="거래 패턴 상세">
                  <DrilldownHistograms
                    holdingPeriodDist={behavior.holdingPeriodDist}
                    positionSizeDist={behavior.positionSizeDist}
                  />
                </SectionCard>
              )}

            {summary.sellTrades === 0 && (
              <AnalysisEmptyState hasTrades={summary.totalTrades > 0} hasSells={summary.sellTrades > 0} />
            )}
          </>
        ) : null}
      </div>
    </PullToRefresh>
  );
}
