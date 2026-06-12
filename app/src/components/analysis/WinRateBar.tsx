"use client";

import { cn } from "@/lib/utils";
import { ProgressTrack } from "@/components/shared/ProgressTrack";
import { pickRateColor } from "@/lib/analysis/rate-color";

interface WinRateBarProps {
  rate: number;
  hasData: boolean;
  emptyLabel?: string;
  muted?: boolean;
}

export function WinRateBar({ rate, hasData, emptyLabel = "결과 없음", muted = false }: WinRateBarProps) {
  if (!hasData) return <div className="text-[11px] text-muted-foreground">{emptyLabel}</div>;
  const { bg, text } = muted
    ? { bg: "bg-muted-foreground/40", text: "text-muted-foreground" }
    : pickRateColor(rate);
  return (
    <div className="flex items-center gap-2">
      <ProgressTrack pct={rate} colorClass={bg} className="flex-1" />
      <span className={cn("text-[12px] tabular-nums font-semibold w-16 text-right", text)}>
        승률 {Math.round(rate)}%
      </span>
    </div>
  );
}
