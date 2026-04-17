import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import type { DashboardTotals } from "@/lib/portfolio";

function PnLText({ value, className }: { value: number; className?: string }) {
  const pos = value > 0;
  const neg = value < 0;
  return (
    <span
      className={cn(
        "tabular-nums",
        pos && "text-[var(--rise)]",
        neg && "text-[var(--fall)]",
        !pos && !neg && "text-foreground",
        className,
      )}
    >
      {pos ? "+" : ""}
      {fmt(value)}원
    </span>
  );
}

interface DashboardSummaryProps {
  totals: DashboardTotals;
}

export function DashboardSummary({ totals }: DashboardSummaryProps) {
  const {
    totalAssets,
    totalEvaluation,
    totalCash,
    totalUnrealizedPnL,
    totalRealizedPnL,
    monthRealizedPnL,
    monthTradeCount,
    missingQuoteTickers,
  } = totals;

  return (
    <div className="px-5 pt-5 pb-1 space-y-4">
      {/* 총 자산 */}
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

      {/* 손익 3-grid */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-2xl bg-muted/60 p-3.5 space-y-0.5">
          <p className="text-[11px] font-semibold text-muted-foreground">평가손익</p>
          <PnLText value={totalUnrealizedPnL} className="text-[15px] font-bold" />
        </div>
        <div className="rounded-2xl bg-muted/60 p-3.5 space-y-0.5">
          <p className="text-[11px] font-semibold text-muted-foreground">확정손익</p>
          <PnLText value={totalRealizedPnL} className="text-[15px] font-bold" />
        </div>
        <div className="rounded-2xl bg-muted/60 p-3.5 space-y-0.5">
          <p className="text-[11px] font-semibold text-muted-foreground">이달 확정</p>
          <PnLText value={monthRealizedPnL} className="text-[15px] font-bold" />
        </div>
      </div>

      {/* 이번 달 거래 수 */}
      {monthTradeCount > 0 && (
        <p className="text-[12px] text-muted-foreground">
          이번 달 거래 <span className="font-semibold text-foreground">{monthTradeCount}건</span>
        </p>
      )}

      {/* 시세 누락 안내 */}
      {missingQuoteTickers.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          시세 미조회: {missingQuoteTickers.slice(0, 3).join(", ")}
          {missingQuoteTickers.length > 3 && ` 외 ${missingQuoteTickers.length - 3}개`} — 평가금액 제외됨
        </p>
      )}
    </div>
  );
}
