"use client";

import { STRATEGY_LABELS } from "@/lib/constants/trading";
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

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.type} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[13px] font-medium text-foreground">
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
              <PnLLine value={item.sumPnL} />
            </span>
          </div>
          <WinRateBar rate={item.winRate} hasData={item.resultCount > 0} />
        </div>
      ))}
    </div>
  );
}
