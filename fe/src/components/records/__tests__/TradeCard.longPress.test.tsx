// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TradeCard } from "../TradeCard";
import type { TradeWithAccount } from "@/lib/trade-utils";

// 롱프레스 회귀 — 진입 직후 click 으로 onSelectToggle 가 호출되어 방금
// 선택된 trade 가 toggle 로 제거되는 버그를 재현/방지한다.
// 원인: TradeCard 의 click 핸들러가 `longPressEnabled && shouldSuppressClick()`
// short-circuit 으로 suppress flag 를 소비하지 못해, enter() 후 리렌더에서
// selectionMode=true 분기가 onSelectToggle 을 실행하던 사례.

const baseTrade: TradeWithAccount = {
  id: "trade-1",
  user_id: "user-1",
  account_id: "account-1",
  asset_name: "삼성전자",
  ticker_symbol: "005930",
  market_type: "STOCK",
  trade_type: "BUY",
  price: 70000,
  quantity: 10,
  total_amount: 700000,
  traded_at: "2026-05-01T00:00:00Z",
  strategy_type: null,
  reasoning_tags: [],
  buy_reason: null,
  sell_reason: null,
  emotion: null,
  result: null,
  profit_loss: null,
  avg_buy_price: null,
  holding_days: null,
  country_code: "KR",
  exchange: "KOSPI",
  commission: 0,
  tax: 0,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

function pointerEvent(type: string, opts: Partial<PointerEventInit> = {}) {
  // jsdom 은 PointerEvent 미지원 → MouseEvent 로 dispatch 하고 isPrimary 등 보강.
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, ...opts });
  Object.defineProperty(event, "isPrimary", { value: true });
  Object.defineProperty(event, "clientX", { value: opts.clientX ?? 0 });
  Object.defineProperty(event, "clientY", { value: opts.clientY ?? 0 });
  return event;
}

describe("TradeCard 롱프레스 → 선택 모드 진입 회귀", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("롱프레스 진입(enter) 후 리렌더되어도 직후 click 으로 onSelectToggle 가 호출되지 않는다", () => {
    const onLongPress = vi.fn();
    const onSelectToggle = vi.fn();
    const onPress = vi.fn();

    // 부모 컴포넌트가 onLongPress 콜백에서 selectionMode 를 true 로 바꾸는 상황을 시뮬레이션.
    const { rerender } = render(
      <TradeCard
        trade={baseTrade}
        onPress={onPress}
        selectionMode={false}
        selected={false}
        onSelectToggle={onSelectToggle}
        onLongPress={onLongPress}
      />,
    );

    const card = screen.getByRole("button");

    // pointerdown → 500ms 경과 → onLongPress 호출
    act(() => {
      card.dispatchEvent(pointerEvent("pointerdown"));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(onLongPress).toHaveBeenCalledTimes(1);

    // 부모가 selectionMode=true 로 전환 (그리고 첫 카드 선택됨)
    rerender(
      <TradeCard
        trade={baseTrade}
        onPress={onPress}
        selectionMode={true}
        selected={true}
        onSelectToggle={onSelectToggle}
        onLongPress={onLongPress}
      />,
    );

    // pointerup + click — 롱프레스에 따라오는 자연스러운 click 이벤트
    act(() => {
      card.dispatchEvent(pointerEvent("pointerup"));
    });
    fireEvent.click(card);

    // suppress flag 가 소비되어 onSelectToggle 가 호출되지 않아야 한다.
    expect(onSelectToggle).not.toHaveBeenCalled();
    expect(onPress).not.toHaveBeenCalled();
  });

  it("일반 모드에서 롱프레스 없는 단순 클릭은 onPress 를 호출한다", () => {
    const onPress = vi.fn();
    const onSelectToggle = vi.fn();
    const onLongPress = vi.fn();

    render(
      <TradeCard
        trade={baseTrade}
        onPress={onPress}
        selectionMode={false}
        selected={false}
        onSelectToggle={onSelectToggle}
        onLongPress={onLongPress}
      />,
    );

    const card = screen.getByRole("button");

    // pointerdown → 짧게 떼기 (threshold 미달) → click
    act(() => {
      card.dispatchEvent(pointerEvent("pointerdown"));
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      card.dispatchEvent(pointerEvent("pointerup"));
    });
    fireEvent.click(card);

    expect(onLongPress).not.toHaveBeenCalled();
    expect(onPress).toHaveBeenCalledTimes(1);
    expect(onSelectToggle).not.toHaveBeenCalled();
  });

  it("선택 모드에서 단순 클릭은 onSelectToggle 를 정상 호출한다", () => {
    const onPress = vi.fn();
    const onSelectToggle = vi.fn();
    const onLongPress = vi.fn();

    render(
      <TradeCard
        trade={baseTrade}
        onPress={onPress}
        selectionMode={true}
        selected={false}
        onSelectToggle={onSelectToggle}
        onLongPress={onLongPress}
      />,
    );

    const card = screen.getByRole("button");
    fireEvent.click(card);

    expect(onSelectToggle).toHaveBeenCalledTimes(1);
    expect(onSelectToggle).toHaveBeenCalledWith("trade-1");
    expect(onPress).not.toHaveBeenCalled();
    expect(onLongPress).not.toHaveBeenCalled();
  });
});
