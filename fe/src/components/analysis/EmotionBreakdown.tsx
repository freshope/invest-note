"use client";

import { EMOTION_LABELS, UNTAGGED_KEY } from "@/lib/constants/trading";
import { BreakdownList } from "./BreakdownList";
import type { EmotionStats } from "@/lib/analysis/aggregate";

interface EmotionBreakdownProps {
  data: EmotionStats[];
}

export function EmotionBreakdown({ data }: EmotionBreakdownProps) {
  return (
    <BreakdownList<EmotionStats>
      data={data}
      emptyMessage="감정 데이터가 없습니다"
      getKey={(d) => d.type}
      isUntagged={(d) => d.type === UNTAGGED_KEY}
      getLabel={(d) => EMOTION_LABELS[d.type] ?? d.type}
      getStats={(d) => ({
        count: d.count,
        sumPnL: d.sumPnL,
        winRate: d.winRate,
        hasData: d.resultCount > 0,
      })}
      emptyRateLabel="결과 미입력"
    />
  );
}
