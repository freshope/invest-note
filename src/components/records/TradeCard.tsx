"use client";

import { useRouter } from "next/navigation";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { cn } from "@/lib/utils";


interface TradeCardProps {
  trade: TradeWithAccount;
  onPress?: () => void;
}

const STRATEGY_LABELS: Record<string, string> = {
  SCALPING: "스캘핑",
  SWING: "스윙",
  LONG_TERM: "장기",
  UNKNOWN: "—",
};

const EMOTION_LABELS: Record<string, string> = {
  CONFIDENT: "확신",
  ANXIOUS: "불안",
  FOMO: "FOMO",
  IMPULSIVE: "충동",
  CALM: "평온",
};

const RESULT_LABELS: Record<string, string> = {
  SUCCESS: "수익",
  FAIL: "손실",
  BREAKEVEN: "본전",
};

export function TradeCard({ trade, onPress }: TradeCardProps) {
  const router = useRouter();
  const isBuy = trade.trade_type === "BUY";

  const price = Number(trade.price).toLocaleString("ko-KR");
  const quantity = Number(trade.quantity);
  const totalAmount = Number(trade.total_amount).toLocaleString("ko-KR");

  return (
    <button
      type="button"
      onClick={() => onPress ? onPress() : router.push(`/records/${trade.id}`)}
      className="w-full text-left rounded-2xl bg-muted/60 overflow-hidden active:scale-[0.99] transition-transform"
    >
      <div className="flex">
        {/* 좌측 컬러 액센트 */}
        <div
          className={cn(
            "w-1 flex-shrink-0 rounded-l-2xl",
            isBuy ? "bg-[var(--rise)]" : "bg-[var(--fall)]"
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
                    ? "bg-[var(--rise)]/10 text-[var(--rise)]"
                    : "bg-[var(--fall)]/10 text-[var(--fall)]"
                )}
              >
                {isBuy ? "매수" : "매도"}
              </span>
            </div>

            {/* 매도 수익/손실 (우측) */}
            {!isBuy && trade.result && (
              <div className={cn(
                "flex-shrink-0 text-right",
                trade.result === "SUCCESS" && "text-[var(--rise)]",
                trade.result === "FAIL" && "text-[var(--fall)]",
                trade.result === "BREAKEVEN" && "text-muted-foreground",
              )}>
                <div className="text-[13px] font-bold">
                  {RESULT_LABELS[trade.result]}
                </div>
                {trade.computed_pnl != null && (
                  <div className="text-[12px] font-semibold tabular-nums">
                    {trade.computed_pnl > 0 ? "+" : ""}{trade.computed_pnl.toLocaleString("ko-KR")}원
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

          {/* 계좌명 */}
          {trade.account && (
            <div className="mt-1 text-[12px] text-muted-foreground">
              {trade.account.name}
              {trade.account.broker ? ` · ${trade.account.broker}` : ""}
            </div>
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
