"use client";

import { formatPnL, signColor } from "@/lib/format";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";
import { LOSS_THRESHOLD, WIN_THRESHOLD } from "@/lib/constants/analysis";
import { PNL_COLORS } from "@/lib/constants/colors";
import { StatCard } from "@/components/shared/StatCard";

interface SummaryCardsProps {
  summary: AnalysisSummary;
}

function classifyWinRate(winRate: number): string {
  if (winRate >= WIN_THRESHOLD) return PNL_COLORS.rise.text;
  if (winRate < LOSS_THRESHOLD) return PNL_COLORS.fall.text;
  return "text-foreground";
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const { totalTrades, sellTrades, winRate, totalProfitLoss } = summary;

  const winRateClass = classifyWinRate(winRate);
  const pnlClass = signColor(totalProfitLoss, "foreground");

  return (
    <div className="grid grid-cols-2 gap-2">
      <StatCard label="총 거래" value={`${totalTrades}건`} />
      <StatCard label="매도 거래" value={`${sellTrades}건`} />
      <StatCard
        label="승률"
        value={sellTrades === 0 ? "-" : `${Math.round(winRate)}%`}
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
