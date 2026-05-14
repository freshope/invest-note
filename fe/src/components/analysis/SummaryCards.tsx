"use client";

import { formatPnL, signColor } from "@/lib/format";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";
import { LOSS_THRESHOLD, RESULT_INPUT_RATE_LOW, WIN_THRESHOLD } from "@/lib/constants/analysis";
import { PNL_COLORS } from "@/lib/constants/colors";
import { StatCard } from "@/components/shared/StatCard";

interface SummaryCardsProps {
  summary: AnalysisSummary;
}

function classifyWinRate(winRate: number, resultInputRate: number): string {
  if (resultInputRate < RESULT_INPUT_RATE_LOW) return "text-muted-foreground";
  if (winRate >= WIN_THRESHOLD) return PNL_COLORS.rise.text;
  if (winRate < LOSS_THRESHOLD) return PNL_COLORS.fall.text;
  return "text-foreground";
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const { totalTrades, sellTrades, winRate, totalProfitLoss, resultInputRate } = summary;

  const winRateClass = classifyWinRate(winRate, resultInputRate);
  const pnlClass = signColor(totalProfitLoss, "foreground");

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
        value={sellTrades === 0 ? "-" : formatPnL(totalProfitLoss)}
        valueClass={pnlClass}
      />
    </div>
  );
}
