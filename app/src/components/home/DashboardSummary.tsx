import { cn } from "@/lib/utils";
import { fmt, fmtCompact, signColor } from "@/lib/format";
import { StatCard } from "@/components/shared/StatCard";
import type { DashboardTotals } from "@/lib/portfolio";

function PnLText({ value }: { value: number }) {
  const rounded = Math.round(value);
  const abs = Math.abs(rounded);
  const sign = rounded > 0 ? "+" : rounded < 0 ? "-" : "";
  const amount = abs >= 10_000_000 ? fmtCompact(abs) : fmt(abs);
  return (
    <span className={cn("whitespace-nowrap", signColor(rounded, "foreground"))}>
      {sign}{amount}원
    </span>
  );
}

interface DashboardProps {
  totals: DashboardTotals;
}

export function DashboardTitle({ totals }: DashboardProps) {
  const { totalAssets, totalEvaluation, totalCash } = totals;
  return (
    <div>
      <p className="text-[13px] font-semibold text-muted-foreground mb-0.5">총 자산</p>
      <p className="text-[32px] font-bold tabular-nums text-foreground leading-none">
        {fmt(totalAssets)}
        <span className="text-[18px] font-bold text-muted-foreground ml-1">원</span>
      </p>
      <p className="text-[13px] text-muted-foreground mt-1 tabular-nums">
        주식 {fmt(totalEvaluation)}원 · 예수금 {fmt(totalCash)}원
      </p>
    </div>
  );
}

export function DashboardBody({ totals }: DashboardProps) {
  const {
    totalUnrealizedPnL,
    totalRealizedPnL,
    monthRealizedPnL,
    monthTradeCount,
    missingQuoteTickers,
  } = totals;

  return (
    <div className="px-5 space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <StatCard label="평가손익" value={<PnLText value={totalUnrealizedPnL} />} />
        <StatCard label="확정손익" value={<PnLText value={totalRealizedPnL} />} />
        <StatCard label="이달 확정" value={<PnLText value={monthRealizedPnL} />} />
      </div>

      {monthTradeCount > 0 && (
        <p className="text-[12px] text-muted-foreground">
          이번 달 거래 <span className="font-semibold text-foreground">{monthTradeCount}건</span>
        </p>
      )}

      {missingQuoteTickers.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          시세 미조회: {missingQuoteTickers.slice(0, 3).join(", ")}
          {missingQuoteTickers.length > 3 && ` 외 ${missingQuoteTickers.length - 3}개`} — 평가금액 제외됨
        </p>
      )}
    </div>
  );
}
