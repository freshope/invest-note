"use client";

import { memo } from "react";
import { format, subDays } from "date-fns";
import { ko } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { STRATEGY_LABELS, ADHERENCE_CONFIG } from "@/lib/constants/trading";
import type { ReactNode } from "react";
import type { StrategyEvaluation } from "@/lib/analysis/strategy-adherence";

interface TradeStrategyResultSectionProps {
  tradedAt: string;
  holdingDays: number | null;
  strategyEvaluation?: StrategyEvaluation | null;
  className?: string;
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[12px] tabular-nums text-foreground">{value}</span>
    </div>
  );
}

export const TradeStrategyResultSection = memo(function TradeStrategyResultSection({
  tradedAt,
  holdingDays,
  strategyEvaluation,
  className,
}: TradeStrategyResultSectionProps) {
  const sellDate = new Date(tradedAt);
  const avgBuyDate = holdingDays != null ? subDays(sellDate, holdingDays) : null;

  return (
    <div className={cn("rounded-2xl bg-muted/60 p-4 space-y-3", className)}>
      <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">
        전략 결과 (자동 계산)
      </p>

      {holdingDays == null ? (
        <p className="text-[12px] text-muted-foreground">보유일 계산 중…</p>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <span className="text-[16px] font-bold tabular-nums">
              보유 {holdingDays}일
            </span>
            {strategyEvaluation && strategyEvaluation.adherence !== "UNKNOWN" && (
              <span className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold border",
                ADHERENCE_CONFIG[strategyEvaluation.adherence].className,
              )}>
                {ADHERENCE_CONFIG[strategyEvaluation.adherence].label}
              </span>
            )}
          </div>

          <div className="rounded-lg bg-background border border-border/60 px-3 py-2.5 space-y-1.5">
            <InfoRow
              label="매도일"
              value={format(sellDate, "yyyy년 M월 d일 (EEE)", { locale: ko })}
            />
            <InfoRow
              label="평균 매수일"
              value={avgBuyDate
                ? `${format(avgBuyDate, "yyyy년 M월 d일 (EEE)", { locale: ko })} · ${holdingDays}일 전`
                : "–"}
            />
            {strategyEvaluation && (
              <>
                <InfoRow
                  label="계획 전략"
                  value={strategyEvaluation.planned
                    ? (STRATEGY_LABELS[strategyEvaluation.planned] ?? strategyEvaluation.planned)
                    : "–"}
                />
                <InfoRow
                  label="실제 전략"
                  value={strategyEvaluation.actual
                    ? (STRATEGY_LABELS[strategyEvaluation.actual] ?? strategyEvaluation.actual)
                    : "–"}
                />
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
});
