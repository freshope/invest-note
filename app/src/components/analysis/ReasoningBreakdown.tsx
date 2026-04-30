"use client";

import { AlertTriangle } from "lucide-react";
import { REASONING_TAG_LABELS, UNTAGGED_KEY } from "@/lib/constants/trading";
import { BreakdownList } from "./BreakdownList";
import type { TagStats, AnalysisSummary } from "@/lib/analysis/aggregate";

interface ReasoningBreakdownProps {
  data: TagStats[];
  summary: Pick<AnalysisSummary, "feelingRate" | "missingTagRate">;
}

export function ReasoningBreakdown({ data, summary }: ReasoningBreakdownProps) {
  const showFeelingWarn = summary.feelingRate >= 40;
  const showMissingWarn = summary.missingTagRate >= 30;

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted-foreground">
        한 거래가 여러 태그에 포함되어 합계가 총 실현손익과 다를 수 있습니다.
      </p>

      <BreakdownList<TagStats>
        data={data}
        emptyMessage="매칭된 태그 데이터가 없습니다"
        getKey={(d) => d.tag}
        isUntagged={(d) => d.tag === UNTAGGED_KEY}
        getLabel={(d) => REASONING_TAG_LABELS[d.tag] ?? d.tag}
        getStats={(d) => ({
          count: d.count,
          sumPnL: d.sumPnL,
          winRate: d.winRate,
          hasData: d.count > 0,
        })}
      />

      {(showFeelingWarn || showMissingWarn) && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 flex gap-2 items-start">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
          <p className="text-[12px] text-amber-700 leading-snug">
            {showFeelingWarn && `'감/직감' 진입 ${Math.round(summary.feelingRate)}% `}
            {showMissingWarn && `근거 태그 누락 ${Math.round(summary.missingTagRate)}%`}
            {(showFeelingWarn || showMissingWarn) && " — 분석 근거를 추가해보세요"}
          </p>
        </div>
      )}
    </div>
  );
}
