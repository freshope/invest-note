"use client";

import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import { AccountChip } from "@/components/shared/AccountChip";
import { TradeTypeBadge } from "@/components/shared/TradeTypeBadge";
import { STRATEGY_LABELS, EMOTION_LABELS, RESULT_LABELS, TRADE_TYPE } from "@/lib/constants/trading";
import { PNL_COLORS, getTradeTypeAccent } from "@/lib/constants/colors";
import { fmt, formatPnL } from "@/lib/format";
import { useLongPress } from "@/hooks/useLongPress";
import { CheckIcon } from "lucide-react";
import type { TradeWithAccount } from "@/lib/trade-utils";

interface TradeCardProps {
  trade: TradeWithAccount;
  // 부모가 카드마다 새 클로저를 만들지 않도록 trade 자체를 인자로 전달한다.
  onPress?: (trade: TradeWithAccount) => void;
  /** 선택 모드 여부. true 면 체크박스가 보이고 카드 탭은 선택 토글로 동작한다. */
  selectionMode?: boolean;
  /** 현재 카드가 선택되었는지. */
  selected?: boolean;
  /** 선택 토글 콜백 (체크박스/카드 탭 공용). */
  onSelectToggle?: (id: string) => void;
  /** 롱프레스 시 호출 — TradeList 가 선택 모드 진입에 사용. */
  onLongPress?: (trade: TradeWithAccount) => void;
}

export const TradeCard = memo(function TradeCard({
  trade,
  onPress,
  selectionMode = false,
  selected = false,
  onSelectToggle,
  onLongPress,
}: TradeCardProps) {
  const isBuy = trade.trade_type === TRADE_TYPE.BUY;

  const price = fmt(Number(trade.price));
  const quantity = Number(trade.quantity);
  const totalAmount = fmt(Number(trade.total_amount));

  // 선택 모드일 때는 롱프레스 의미 없음 (카드 탭이 곧 토글).
  const longPressEnabled = !selectionMode && !!onLongPress;
  const longPress = useLongPress({
    onLongPress: () => {
      if (longPressEnabled) onLongPress?.(trade);
    },
  });

  // 롱프레스 비활성일 때는 핸들러 부착 자체를 생략 (불필요한 listener 회피).
  const pointerHandlers = longPressEnabled
    ? {
        onPointerDown: longPress.onPointerDown,
        onPointerMove: longPress.onPointerMove,
        onPointerUp: longPress.onPointerUp,
        onPointerCancel: longPress.onPointerCancel,
        onPointerLeave: longPress.onPointerLeave,
      }
    : undefined;

  const handleClick = () => {
    // suppress flag 는 항상 소비해야 한다 — 롱프레스가 enter() 를 호출해
    // selectionMode=true 가 되면 다음 렌더에서 longPressEnabled=false 라
    // 게이트로 묶으면 flag 가 남아 카드 onSelectToggle 가 잘못 실행된다.
    // useLongPress 는 자체적으로 triggered 되지 않으면 flag 가 false 라 안전.
    if (longPress.shouldSuppressClick()) return;
    if (selectionMode) {
      onSelectToggle?.(trade.id);
      return;
    }
    onPress?.(trade);
  };

  // 체크박스 클릭은 카드 onClick 으로도 잡히지만, Checkbox 의 stopPropagation 없이 자연스럽게 토글되게 둔다.
  // selectionMode 일 때 카드 onClick → onSelectToggle 가 호출되므로 Checkbox 자체 onCheckedChange 는 비워둔다.
  const cardLabel = useMemo(
    () =>
      selectionMode
        ? `${trade.asset_name} ${selected ? "선택 해제" : "선택"}`
        : undefined,
    [selectionMode, selected, trade.asset_name],
  );

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={selectionMode ? selected : undefined}
      aria-label={cardLabel}
      {...pointerHandlers}
      className={cn(
        "w-full text-left rounded-2xl bg-muted/60 overflow-hidden active:scale-[0.99] transition-transform",
        selectionMode && selected && "ring-2 ring-primary",
      )}
    >
      <div className="flex">
        {/* 좌측 컬러 액센트 */}
        <div
          className={cn(
            "w-1 flex-shrink-0 rounded-l-2xl",
            getTradeTypeAccent(trade.trade_type).bg,
          )}
        />

        {selectionMode && (
          <div className="flex items-center justify-center pl-3 pr-1">
            <span
              aria-hidden
              className={cn(
                "size-4 shrink-0 rounded-[4px] border flex items-center justify-center",
                selected ? "bg-primary border-primary" : "bg-background border-input",
              )}
            >
              {selected && <CheckIcon className="size-3 text-primary-foreground" strokeWidth={3} />}
            </span>
          </div>
        )}

        <div className="flex-1 p-4">
          <div className="flex items-start justify-between gap-2">
            {/* 종목명 + 매수/매도 뱃지 */}
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[16px] font-bold text-foreground truncate">{trade.asset_name}</span>
              <TradeTypeBadge tradeType={trade.trade_type} size="sm" />
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
});
