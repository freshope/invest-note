"use client";

import { memo, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type MouseEvent } from "react";
import { useSwipeable } from "react-swipeable";
import { cn } from "@/lib/utils";
import { AccountChip } from "@/components/shared/AccountChip";
import { TradeTypeBadge } from "@/components/shared/TradeTypeBadge";
import { STRATEGY_LABELS, EMOTION_LABELS, RESULT_LABELS, TRADE_TYPE } from "@/lib/constants/trading";
import { PNL_COLORS, getTradeTypeAccent } from "@/lib/constants/colors";
import { fmt, formatPnL } from "@/lib/format";
import { CheckIcon, Trash2Icon } from "lucide-react";
import type { TradeWithAccount } from "@/lib/trade-utils";

// 우측 트레일링 액션(삭제) 버튼 폭. translateX 값과 동일하게 유지한다.
const ACTION_WIDTH_PX = 88;

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
  /** 스와이프 열림 상태 (TradeList 가 단일 ID로 관리). */
  swipeOpen?: boolean;
  /**
   * 스와이프 열림 상태 변경 요청. id 를 함께 전달해 부모가 useCallback 으로
   * 안정화해도 memo 가 유지되도록 한다.
   */
  onSwipeOpenChange?: (id: string, open: boolean) => void;
  /** 삭제 버튼 탭 콜백. TradeList 가 다이얼로그를 띄운다. */
  onRequestDelete?: (trade: TradeWithAccount) => void;
}

export const TradeCard = memo(function TradeCard({
  trade,
  onPress,
  selectionMode = false,
  selected = false,
  onSelectToggle,
  swipeOpen = false,
  onSwipeOpenChange,
  onRequestDelete,
}: TradeCardProps) {
  const isBuy = trade.trade_type === TRADE_TYPE.BUY;

  const price = fmt(Number(trade.price));
  const quantity = Number(trade.quantity);
  const totalAmount = fmt(Number(trade.total_amount));

  // 선택 모드에서는 스와이프 비활성 (체크박스 토글이 우선).
  const swipeEnabled = !selectionMode && !!onSwipeOpenChange;

  // 드래그 중 실시간 translateX. onSwiped 콜백에서 최종값을 읽어 open/close 결정.
  const [dragOffset, setDragOffset] = useState(0);
  const dragOffsetRef = useRef(0);
  // 스와이프 직후 브라우저가 합성 click 을 카드 컨텐츠에 발사하면 handleCardClick 이
  // 방금 연 카드를 즉시 닫는다. 짧은 윈도우 동안 click 1회 억제로 가드.
  const suppressClickRef = useRef(false);

  const swipeHandlers = useSwipeable({
    onSwipeStart: () => {
      // 스와이프로 인식되는 순간 click 1회 억제 (라이브러리는 left/right 임계 통과시에만 호출).
      if (!swipeEnabled) return;
      suppressClickRef.current = true;
    },
    onSwiping: (e) => {
      if (!swipeEnabled) return;
      // 이미 열려있는 카드는 -ACTION_WIDTH 에서 추적 시작. 0(닫힘) ~ -ACTION*1.2 로 clamp.
      const base = swipeOpen ? -ACTION_WIDTH_PX : 0;
      const next = Math.min(0, Math.max(-ACTION_WIDTH_PX * 1.2, base + e.deltaX));
      dragOffsetRef.current = next;
      setDragOffset(next);
    },
    onSwiped: () => {
      if (!swipeEnabled) return;
      const final = dragOffsetRef.current;
      dragOffsetRef.current = 0;
      setDragOffset(0);
      // 절반 이상 끌렸으면 열기 그 외엔 닫기 — iOS Mail / 토스 표준.
      const shouldOpen = final < -ACTION_WIDTH_PX / 2;
      onSwipeOpenChange?.(trade.id, shouldOpen);
    },
    // 수직 임계를 Infinity 로 두면 세로 의도가 절대 swipe 로 판정되지 않아 native scroll 이 항상 이긴다.
    // 수평은 작은 값으로 두어 가로 스와이프 인식은 빠르게 유지.
    delta: { left: 12, right: 12, up: Infinity, down: Infinity },
    trackTouch: true,
    trackMouse: false,
    preventScrollOnSwipe: true,
  });

  const isDragging = dragOffset !== 0;
  const transformStyle: CSSProperties = isDragging
    ? { transform: `translateX(${dragOffset}px)` }
    : { transform: swipeOpen ? `translateX(-${ACTION_WIDTH_PX}px)` : "translateX(0)" };

  const handleCardClick = () => {
    // 스와이프 직후 합성 click 을 1회 소비. 카드가 즉시 닫히는 현상 방지.
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    // 스와이프가 열려 있으면 탭은 "닫기" 로만 동작한다 (iOS Mail 표준).
    if (swipeOpen) {
      onSwipeOpenChange?.(trade.id, false);
      return;
    }
    if (selectionMode) {
      onSelectToggle?.(trade.id);
      return;
    }
    onPress?.(trade);
  };

  const handleCardKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    handleCardClick();
  };

  const handleDeleteClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onRequestDelete?.(trade);
  };

  const cardLabel = useMemo(
    () =>
      selectionMode
        ? `${trade.asset_name} ${selected ? "선택 해제" : "선택"}`
        : undefined,
    [selectionMode, selected, trade.asset_name],
  );

  return (
    <div className="relative overflow-hidden rounded-2xl bg-muted active:scale-[0.99] transition-transform">
      {/* 트레일링 액션 레이어 — 우측 고정. 컨텐츠가 translate 되며 노출된다. */}
      <button
        type="button"
        onClick={handleDeleteClick}
        tabIndex={swipeOpen ? 0 : -1}
        aria-hidden={!swipeOpen}
        aria-label={`${trade.asset_name} 삭제`}
        style={{ width: ACTION_WIDTH_PX }}
        className="absolute inset-y-0 right-0 flex flex-col items-center justify-center gap-1 bg-destructive text-white active:bg-destructive/90"
      >
        <Trash2Icon className="size-5" strokeWidth={2} />
        <span className="text-[12px] font-semibold">삭제</span>
      </button>

      {/* 컨텐츠 레이어 — 스와이프로 translateX. 드래그 중에는 transition 끔. */}
      <div
        {...(swipeEnabled ? swipeHandlers : {})}
        style={transformStyle}
        className={cn(
          "relative touch-pan-y",
          isDragging ? "transition-none" : "transition-transform duration-200 ease-out",
        )}
      >
        <div
          role="button"
          tabIndex={0}
          onClick={handleCardClick}
          onKeyDown={handleCardKey}
          aria-pressed={selectionMode ? selected : undefined}
          aria-label={cardLabel}
          className={cn(
            "w-full text-left rounded-l-2xl bg-muted overflow-hidden",
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
        </div>
      </div>
    </div>
  );
});
