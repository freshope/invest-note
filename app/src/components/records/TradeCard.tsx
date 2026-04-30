"use client";

import type { Trade, Account } from "@/types/database";
import { cn } from "@/lib/utils";
import { AccountChip } from "@/components/shared/AccountChip";
import { STRATEGY_LABELS, EMOTION_LABELS, RESULT_LABELS } from "@/lib/constants/trading";
import { PNL_COLORS } from "@/lib/constants/colors";
import { fmt, formatPnL } from "@/lib/format";

interface TradeCardProps {
  trade: Trade & { account?: Pick<Account, "name" | "broker"> };
  onPress?: () => void;
}

export function TradeCard({ trade, onPress }: TradeCardProps) {
  const isBuy = trade.trade_type === "BUY";

  const price = fmt(Number(trade.price));
  const quantity = Number(trade.quantity);
  const totalAmount = fmt(Number(trade.total_amount));

  return (
    <button
      type="button"
      onClick={() => onPress?.()}
      className="w-full text-left rounded-2xl bg-muted/60 overflow-hidden active:scale-[0.99] transition-transform"
    >
      <div className="flex">
        {/* 좌측 컬러 액센트 */}
        <div
          className={cn(
            "w-1 flex-shrink-0 rounded-l-2xl",
            isBuy ? PNL_COLORS.rise.bg : PNL_COLORS.fall.bg
          )}
        />

        <div className="flex-1 p-4">
          <div className="flex items-start justify-between gap-2">
            {/* 종목명 + 매수/매도 뱃지 */}
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[16px] font-bold text-foreground truncate">{trade.asset_name}</span>
              <span
                className={cn(
                  "text-[11px] font-bold px-1.5 py-0.5 rounded-md flex-shrink-0",
                  isBuy
                    ? cn(PNL_COLORS.rise.bgSoft, PNL_COLORS.rise.text)
                    : cn(PNL_COLORS.fall.bgSoft, PNL_COLORS.fall.text)
                )}
              >
                {isBuy ? "매수" : "매도"}
              </span>
            </div>

            {/* 매도 수익/손실 (우측) */}
            {!isBuy && trade.result && (
              <div className={cn(
                "flex-shrink-0 text-right",
                trade.result === "SUCCESS" && PNL_COLORS.rise.text,
                trade.result === "FAIL" && PNL_COLORS.fall.text,
                trade.result === "BREAKEVEN" && "text-muted-foreground",
              )}>
                <div className="text-[13px] font-bold">
                  {RESULT_LABELS[trade.result]}
                </div>
                {trade.profit_loss != null && (
                  <div className="text-[12px] font-semibold tabular-nums">
                    {formatPnL(Number(trade.profit_loss))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 가격 × 수량 = 총액 */}
          <div className="mt-1.5 text-[13px] text-muted-foreground">
            {price}원 × {quantity}주 ={" "}
            <span className="font-semibold text-foreground">{totalAmount}원</span>
          </div>

          {trade.account && (
            <AccountChip
              account={trade.account}
              size="sm"
              className="mt-1 text-[12px] text-muted-foreground"
            />
          )}

          {/* 메타데이터 뱃지들 */}
          {(trade.strategy_type || trade.emotion) && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {trade.strategy_type && trade.strategy_type !== "UNKNOWN" && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                  {STRATEGY_LABELS[trade.strategy_type]}
                </span>
              )}
              {trade.emotion && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
                  {EMOTION_LABELS[trade.emotion]}
                </span>
              )}
            </div>
          )}

          {/* 매수/매도 이유 */}
          {(isBuy ? trade.buy_reason : trade.sell_reason) && (
            <p className="mt-1.5 text-[12px] text-muted-foreground truncate">
              {isBuy ? trade.buy_reason : trade.sell_reason}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}
