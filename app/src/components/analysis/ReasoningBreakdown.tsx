"use client";

import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import { AlertTriangle } from "lucide-react";
import { REASONING_TAGS } from "@/components/records/constants";
import { WinRateBar } from "./WinRateBar";
import type { TagStats, AnalysisSummary } from "@/lib/analysis/aggregate";

interface ReasoningBreakdownProps {
  data: TagStats[];
  summary: Pick<AnalysisSummary, "feelingRate" | "missingTagRate">;
}

export function ReasoningBreakdown({ data, summary }: ReasoningBreakdownProps) {
  const labelMap = Object.fromEntries(REASONING_TAGS.map((t) => [t.value, t.label]));
  const showFeelingWarn = summary.feelingRate >= 40;
  const showMissingWarn = summary.missingTagRate >= 30;

  return (
    <div className="space-y-3">
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

      {data.length === 0 ? (
        <div className="text-[13px] text-muted-foreground text-center py-4">
          매칭된 태그 데이터가 없습니다
        </div>
      ) : (
        data.map((item) => (
          <div key={item.tag} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-foreground">
                {labelMap[item.tag] ?? item.tag}
              </span>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {item.count}건
                {item.avgPnL !== 0 && (
                  <span className={cn("ml-1.5", item.avgPnL > 0 ? "text-[var(--rise)]" : "text-[var(--fall)]")}>
                    {item.avgPnL > 0 ? "+" : ""}{fmt(Math.round(item.avgPnL))}원
                  </span>
                )}
              </span>
            </div>
            <WinRateBar rate={item.winRate} hasData={item.count > 0} />
          </div>
        ))
      )}
    </div>
  );
}
