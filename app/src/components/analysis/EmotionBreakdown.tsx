"use client";

import { cn } from "@/lib/utils";
import { EMOTION_LABELS, UNTAGGED_KEY } from "@/lib/constants/trading";
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

  const others = data.filter((d) => d.type !== UNTAGGED_KEY);
  const untagged = data.filter((d) => d.type === UNTAGGED_KEY);
  const sortedData = [...others, ...untagged];

  return (
    <div className="space-y-3">
      {sortedData.map((item) => {
        const isMuted = item.type === UNTAGGED_KEY;
        return (
          <div key={item.type} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className={cn("text-[13px] font-medium", isMuted ? "text-muted-foreground" : "text-foreground")}>
                {EMOTION_LABELS[item.type] ?? item.type}
              </span>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {item.count}건
                <PnLLine value={item.sumPnL} muted={isMuted} />
              </span>
            </div>
            <WinRateBar rate={item.winRate} hasData={item.resultCount > 0} emptyLabel="결과 미입력" muted={isMuted} />
          </div>
        );
      })}
    </div>
  );
}
