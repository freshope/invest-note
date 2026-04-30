"use client";

import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { REASONING_TAG_LABELS, UNTAGGED_KEY } from "@/lib/constants/trading";
import { PnLLine } from "./PnLLine";
import { WinRateBar } from "./WinRateBar";
import type { TagStats, AnalysisSummary } from "@/lib/analysis/aggregate";

interface ReasoningBreakdownProps {
  data: TagStats[];
  summary: Pick<AnalysisSummary, "feelingRate" | "missingTagRate">;
}

export function ReasoningBreakdown({ data, summary }: ReasoningBreakdownProps) {
  const showFeelingWarn = summary.feelingRate >= 40;
  const showMissingWarn = summary.missingTagRate >= 30;

  const others = data.filter((d) => d.tag !== UNTAGGED_KEY);
  const untagged = data.filter((d) => d.tag === UNTAGGED_KEY);
  const sortedData = [...others, ...untagged];

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

      {sortedData.length === 0 ? (
        <div className="text-[13px] text-muted-foreground text-center py-4">
          매칭된 태그 데이터가 없습니다
        </div>
      ) : (
        <>
          {sortedData.map((item) => {
            const isMuted = item.tag === UNTAGGED_KEY;
            return (
              <div key={item.tag} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className={cn("text-[13px] font-medium", isMuted ? "text-muted-foreground" : "text-foreground")}>
                    {REASONING_TAG_LABELS[item.tag] ?? item.tag}
                  </span>
                  <span className="text-[11px] text-muted-foreground tabular-nums">
                    {item.count}건
                    <PnLLine value={item.sumPnL} muted={isMuted} />
                  </span>
                </div>
                <WinRateBar rate={item.winRate} hasData={item.count > 0} muted={isMuted} />
              </div>
            );
          })}
          <p className="text-[11px] text-muted-foreground pt-1">
            한 거래가 여러 태그에 포함되어 합계가 총 실현손익과 다를 수 있습니다.
          </p>
        </>
      )}
    </div>
  );
}
