"use client";

import { cn } from "@/lib/utils";
import { WIN_THRESHOLD, LOSS_THRESHOLD } from "@/lib/constants/analysis";
import { PNL_COLORS } from "@/lib/constants/colors";

interface WinRateBarProps {
  rate: number;
  hasData: boolean;
  emptyLabel?: string;
  muted?: boolean;
}

export function WinRateBar({ rate, hasData, emptyLabel = "결과 없음", muted = false }: WinRateBarProps) {
  if (!hasData) return <div className="text-[11px] text-muted-foreground">{emptyLabel}</div>;
  const barColor = muted
    ? "bg-muted-foreground/40"
    : rate >= WIN_THRESHOLD
      ? PNL_COLORS.rise.bg
      : rate < LOSS_THRESHOLD
        ? PNL_COLORS.fall.bg
        : "bg-amber-400";
  const textColor = muted
    ? "text-muted-foreground"
    : rate >= WIN_THRESHOLD
      ? PNL_COLORS.rise.text
      : rate < LOSS_THRESHOLD
        ? PNL_COLORS.fall.text
        : "text-amber-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full", barColor)} style={{ width: `${rate}%` }} />
      </div>
      <span className={cn("text-[12px] tabular-nums font-semibold w-16 text-right", textColor)}>
        승률 {Math.round(rate)}%
      </span>
    </div>
  );
}
