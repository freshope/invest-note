"use client";

import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import { ADHERENCE_CONFIG } from "@/lib/constants/trading";
import { WinRateBar } from "./WinRateBar";
import type { StrategyAdherenceStats } from "@/lib/analysis/aggregate";

interface StrategyAdherencePanelProps {
  rate: number;
  data: StrategyAdherenceStats[];
}

export function StrategyAdherencePanel({ rate, data }: StrategyAdherencePanelProps) {
  const judged = data.filter((item) => item.type !== "UNKNOWN").reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px] text-muted-foreground">전략 준수율</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">계획 전략과 실제 보유일 기준</p>
        </div>
        <div className="text-right">
          <p className="text-[20px] font-bold tabular-nums text-foreground">
            {judged > 0 ? `${Math.round(rate)}%` : "-"}
          </p>
          <p className="text-[11px] text-muted-foreground">{judged}건 판정</p>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="text-[13px] text-muted-foreground text-center py-4">
          전략 준수 데이터가 없습니다
        </div>
      ) : (
        data.map((item) => {
          const config = ADHERENCE_CONFIG[item.type];
          return (
            <div key={item.type} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className={cn("text-[12px] font-semibold", config.className)}>
                  {config.label}
                </span>
                <span className="text-[11px] text-muted-foreground tabular-nums">
                  {item.count}건
                  {item.avgPnL !== 0 && (
                    <span className={cn("ml-1.5", item.avgPnL > 0 ? "text-[var(--rise)]" : "text-[var(--fall)]")}>
                      {item.avgPnL > 0 ? "+" : ""}{fmt(Math.round(item.avgPnL))}원
                    </span>
                  )}
                </span>
              </div>
              <WinRateBar rate={item.winRate} hasData={item.resultCount > 0} />
            </div>
          );
        })
      )}
    </div>
  );
}
