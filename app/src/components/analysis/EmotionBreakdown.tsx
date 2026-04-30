"use client";

import { EMOTION_LABELS } from "@/lib/constants/trading";
import { PnLLine } from "./PnLLine";
import { WinRateBar } from "./WinRateBar";
import type { EmotionStats } from "@/lib/analysis/aggregate";

interface EmotionBreakdownProps {
  data: EmotionStats[];
}

export function EmotionBreakdown({ data }: EmotionBreakdownProps) {
  if (data.length === 0) {
    return (
      <div className="text-[13px] text-muted-foreground text-center py-6">
        감정 데이터가 없습니다
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.type} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-medium text-foreground">
              {EMOTION_LABELS[item.type] ?? item.type}
            </span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {item.count}건
              <PnLLine value={item.sumPnL} />
            </span>
          </div>
          <WinRateBar rate={item.winRate} hasData={item.resultCount > 0} emptyLabel="결과 미입력" />
        </div>
      ))}
    </div>
  );
}
