"use client";

import { cn } from "@/lib/utils";

interface WinRateBarProps {
  rate: number;
  hasData: boolean;
  emptyLabel?: string;
}

export function WinRateBar({ rate, hasData, emptyLabel = "결과 없음" }: WinRateBarProps) {
  if (!hasData) return <div className="text-[11px] text-muted-foreground">{emptyLabel}</div>;
  const color = rate >= 60 ? "bg-[var(--rise)]" : rate < 40 ? "bg-[var(--fall)]" : "bg-amber-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${rate}%` }} />
      </div>
      <span className={cn("text-[12px] tabular-nums font-semibold w-8 text-right",
        rate >= 60 ? "text-[var(--rise)]" : rate < 40 ? "text-[var(--fall)]" : "text-amber-500",
      )}>
        {Math.round(rate)}%
      </span>
    </div>
  );
}
