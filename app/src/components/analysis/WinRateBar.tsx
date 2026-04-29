"use client";

import { cn } from "@/lib/utils";
import { WIN_THRESHOLD, LOSS_THRESHOLD } from "@/lib/constants/analysis";
import { PNL_COLORS } from "@/lib/constants/colors";

interface WinRateBarProps {
  rate: number;
  hasData: boolean;
  emptyLabel?: string;
}

export function WinRateBar({ rate, hasData, emptyLabel = "결과 없음" }: WinRateBarProps) {
  if (!hasData) return <div className="text-[11px] text-muted-foreground">{emptyLabel}</div>;
  const color = rate >= WIN_THRESHOLD ? PNL_COLORS.rise.bg : rate < LOSS_THRESHOLD ? PNL_COLORS.fall.bg : "bg-amber-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${rate}%` }} />
      </div>
      <span className={cn("text-[12px] tabular-nums font-semibold w-8 text-right",
        rate >= WIN_THRESHOLD ? PNL_COLORS.rise.text : rate < LOSS_THRESHOLD ? PNL_COLORS.fall.text : "text-amber-500",
      )}>
        {Math.round(rate)}%
      </span>
    </div>
  );
}
