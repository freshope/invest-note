"use client";

import { STRATEGY_LABELS, STRATEGY_UNKNOWN_KEY } from "@/lib/constants/trading";
import { BreakdownList } from "./BreakdownList";
import type { StrategyStats } from "@/lib/analysis/aggregate";

interface StrategyBreakdownProps {
  data: StrategyStats[];
}

export function StrategyBreakdown({ data }: StrategyBreakdownProps) {
  return (
    <BreakdownList<StrategyStats>
      data={data}
      emptyMessage="전략 데이터가 없습니다"
      getKey={(d) => d.type}
      isUntagged={(d) => d.type === STRATEGY_UNKNOWN_KEY}
      getLabel={(d) => STRATEGY_LABELS[d.type] ?? d.type}
      getStats={(d) => ({
        count: d.count,
        sumPnL: d.sumPnL,
        winRate: d.winRate,
        hasData: d.resultCount > 0,
      })}
      renderMeta={(d) =>
        d.avgHoldingDays > 0 ? (
          <span className="text-[11px] text-muted-foreground ml-1.5">
            평균 {Math.round(d.avgHoldingDays)}일 보유
          </span>
        ) : null
      }
    />
  );
}
