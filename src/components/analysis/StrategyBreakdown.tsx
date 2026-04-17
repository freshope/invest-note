"use client";

import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import { STRATEGIES } from "@/components/records/constants";
import type { StrategyStats } from "@/lib/analysis/aggregate";

function WinRateBar({ rate, hasData }: { rate: number; hasData: boolean }) {
  if (!hasData) return <div className="text-[11px] text-muted-foreground">결과 없음</div>;
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

interface StrategyBreakdownProps {
  data: StrategyStats[];
}

export function StrategyBreakdown({ data }: StrategyBreakdownProps) {
  if (data.length === 0) {
    return (
      <div className="text-[13px] text-muted-foreground text-center py-6">
        전략 데이터가 없습니다
      </div>
    );
  }

  const labelMap = Object.fromEntries(STRATEGIES.map((s) => [s.value, s.label]));

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.type} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[13px] font-medium text-foreground">
                {labelMap[item.type] ?? item.type}
              </span>
              {item.avgHoldingDays > 0 && (
                <span className="text-[11px] text-muted-foreground ml-1.5">
                  평균 {Math.round(item.avgHoldingDays)}일 보유
                </span>
              )}
            </div>
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
      ))}
    </div>
  );
}
