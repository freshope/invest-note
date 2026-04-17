"use client";

import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";

function StatCard({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-2xl bg-muted/60 p-3.5 space-y-0.5">
      <p className="text-[11px] font-semibold text-muted-foreground">{label}</p>
      <p className={cn("text-[15px] font-bold tabular-nums leading-snug", valueClass)}>{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

interface SummaryCardsProps {
  summary: AnalysisSummary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const { totalTrades, sellTrades, winRate, totalProfitLoss, resultInputRate } = summary;

  const winRateClass =
    resultInputRate < 50
      ? "text-muted-foreground"
      : winRate >= 60
        ? "text-[var(--rise)]"
        : winRate < 40
          ? "text-[var(--fall)]"
          : "text-foreground";

  const pnlClass =
    totalProfitLoss > 0
      ? "text-[var(--rise)]"
      : totalProfitLoss < 0
        ? "text-[var(--fall)]"
        : "text-foreground";

  return (
    <div className="grid grid-cols-2 gap-2">
      <StatCard label="총 거래" value={`${totalTrades}건`} />
      <StatCard label="매도 거래" value={`${sellTrades}건`} />
      <StatCard
        label="승률"
        value={resultInputRate === 0 ? "-" : `${Math.round(winRate)}%`}
        sub={resultInputRate < 100 && sellTrades > 0 ? `입력률 ${Math.round(resultInputRate)}%` : undefined}
        valueClass={winRateClass}
      />
      <StatCard
        label="총 실현손익"
        value={sellTrades === 0 ? "-" : `${totalProfitLoss >= 0 ? "+" : ""}${fmt(Math.round(totalProfitLoss))}원`}
        valueClass={pnlClass}
      />
    </div>
  );
}
