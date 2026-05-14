import { cn } from "@/lib/utils";
import { fmt, formatPnL, signColor } from "@/lib/format";
import { PNL_COLORS } from "@/lib/constants/colors";
import type { TradeResult } from "@/types/database";
import type { TradeSummary } from "@/lib/api-client";

const RESULT_BADGE: Record<TradeResult, { label: string; classes: string }> = {
  SUCCESS: {
    label: "수익 ✅",
    classes: cn(PNL_COLORS.rise.bgSoft, PNL_COLORS.rise.text, PNL_COLORS.rise.borderSoft),
  },
  FAIL: {
    label: "손실 ❌",
    classes: cn(PNL_COLORS.fall.bgSoft, PNL_COLORS.fall.text, PNL_COLORS.fall.borderSoft),
  },
  BREAKEVEN: {
    label: "본전 ➖",
    classes: "bg-muted text-foreground border-border",
  },
};
const RESULT_BADGE_FALLBACK = { label: "–", classes: "bg-muted text-muted-foreground border-border" };

interface SellResultSectionProps {
  summary: TradeSummary | undefined;
}

export function SellResultSection({ summary }: SellResultSectionProps) {
  const badge = summary?.result ? RESULT_BADGE[summary.result] : RESULT_BADGE_FALLBACK;
  return (
    <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
      <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">
        거래 결과 (자동 계산)
      </p>
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-bold border",
            badge.classes,
          )}
        >
          {badge.label}
        </span>
        {summary?.pnl != null && (
          <span className={cn("text-[16px] font-bold tabular-nums", signColor(summary.pnl, "none"))}>
            {formatPnL(summary.pnl)}
          </span>
        )}
      </div>
      {summary?.breakdown && (
        <div className="rounded-lg bg-background border border-border/60 px-3 py-2.5 space-y-1.5">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted-foreground">
              {`매도금액 (${fmt(summary.breakdown.sellPrice)}원 × ${summary.breakdown.quantity}주)`}
            </span>
            <span className="text-[12px] tabular-nums text-foreground">
              +{fmt(summary.breakdown.sellAmount)}원
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted-foreground">
              {`매수비용 (평단 ${fmt(Math.round(summary.breakdown.avgCostPrice))}원 × ${summary.breakdown.quantity}주)`}
            </span>
            <span className="text-[12px] tabular-nums text-foreground">
              -{fmt(summary.breakdown.costBasis)}원
            </span>
          </div>
          {summary.breakdown.commission > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-[11px] text-muted-foreground">수수료</span>
              <span className="text-[12px] tabular-nums text-foreground">
                -{fmt(summary.breakdown.commission)}원
              </span>
            </div>
          )}
          {summary.breakdown.tax > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-[11px] text-muted-foreground">세금</span>
              <span className="text-[12px] tabular-nums text-foreground">
                -{fmt(summary.breakdown.tax)}원
              </span>
            </div>
          )}
          <div className="border-t border-border/60 pt-1.5 flex justify-between items-center">
            <span className="text-[12px] font-semibold text-foreground">실현손익</span>
            <span
              className={cn(
                "text-[13px] font-bold tabular-nums",
                summary.pnl != null && signColor(summary.pnl, "none"),
              )}
            >
              {summary.pnl != null ? formatPnL(summary.pnl) : "–"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
