"use client";

import { cn } from "@/lib/utils";
import { STRATEGY_LABELS, STRATEGY_UNKNOWN_KEY } from "@/lib/constants/trading";
import { PnLLine } from "./PnLLine";
import { WinRateBar } from "./WinRateBar";
import type { StrategyStats } from "@/lib/analysis/aggregate";

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

  const others = data.filter((d) => d.type !== STRATEGY_UNKNOWN_KEY);
  const untagged = data.filter((d) => d.type === STRATEGY_UNKNOWN_KEY);
  const sortedData = [...others, ...untagged];

  return (
    <div className="space-y-3">
      {sortedData.map((item) => {
        const isMuted = item.type === STRATEGY_UNKNOWN_KEY;
        return (
          <div key={item.type} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div>
                <span className={cn("text-[13px] font-medium", isMuted ? "text-muted-foreground" : "text-foreground")}>
                  {STRATEGY_LABELS[item.type] ?? item.type}
                </span>
                {item.avgHoldingDays > 0 && (
                  <span className="text-[11px] text-muted-foreground ml-1.5">
                    평균 {Math.round(item.avgHoldingDays)}일 보유
                  </span>
                )}
              </div>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {item.count}건
                <PnLLine value={item.sumPnL} muted={isMuted} />
              </span>
            </div>
            <WinRateBar rate={item.winRate} hasData={item.resultCount > 0} muted={isMuted} />
          </div>
        );
      })}
    </div>
  );
}
