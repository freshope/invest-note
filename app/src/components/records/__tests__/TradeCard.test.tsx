// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TradeCard } from "../TradeCard";
import type { TradeWithAccount } from "@/lib/trade-utils";
import type { StockMeta } from "@/lib/api-client";

const trade: TradeWithAccount = {
  id: "t1",
  user_id: "u1",
  account_id: "a1",
  asset_name: "삼성전자",
  ticker_symbol: "005930",
  market_type: "STOCK",
  trade_type: "BUY",
  price: 60000,
  quantity: 10,
  total_amount: 600000,
  traded_at: "2026-06-01T00:00:00Z",
  strategy_type: null,
  reasoning_tags: [],
  custom_tags: [],
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
  origin: "MANUAL",
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

const meta: StockMeta = {
  market: "KOSPI",
  marcap_rank: 1,
  nps_holding: "major",
  nps_as_of: "2026-03-31",
  us_index: null,
};

afterEach(cleanup);

describe("TradeCard 거래내역서 배지", () => {
  it("origin이 IMPORT면 '거래내역서' 배지를 노출한다", () => {
    render(<TradeCard trade={{ ...trade, origin: "IMPORT" }} meta={meta} onPress={vi.fn()} />);
    expect(screen.getByText("거래내역서")).toBeDefined();
  });

  it("origin이 MANUAL이면 '거래내역서' 배지를 노출하지 않는다", () => {
    render(<TradeCard trade={trade} meta={meta} onPress={vi.fn()} />);
    expect(screen.queryByText("거래내역서")).toBeNull();
  });
});

describe("TradeCard 메타 뱃지", () => {
  it("뱃지를 탭하면 바텀시트만 열리고 카드 onPress는 호출되지 않는다", async () => {
    const onPress = vi.fn();
    const user = userEvent.setup();
    render(<TradeCard trade={trade} meta={meta} onPress={onPress} />);

    await user.click(screen.getByRole("button", { name: "시총 1위" }));

    // 시트에는 이 종목에 표시된 뱃지 전체 설명이 한 페이지로 나온다.
    // 연금은 어느 쪽이든 보유/5%+ 두 단계 설명을 모두 보여준다.
    expect(await screen.findByText("뱃지 안내")).toBeDefined();
    expect(screen.getByText("상장 시장")).toBeDefined();
    expect(screen.getByText("시가총액 순위")).toBeDefined();
    expect(screen.getByText("국민연금 보유")).toBeDefined();
    expect(screen.getByText("국민연금 대량보유")).toBeDefined();
    expect(onPress).not.toHaveBeenCalled();
  });

  it("시트의 오버레이를 탭하면 시트가 닫히고 카드 onPress는 호출되지 않는다", async () => {
    // vaul 은 body 로 portal 되지만 React 합성 이벤트는 React 트리를 따라
    // 카드 onClick 까지 버블되므로, 닫기 경로의 전파 차단을 명시 검증한다.
    // 동시에 dismiss(document 레벨 pointerdown 리스너)는 막으면 안 된다.
    const onPress = vi.fn();
    const user = userEvent.setup();
    render(<TradeCard trade={trade} meta={meta} onPress={onPress} />);

    await user.click(screen.getByRole("button", { name: "시총 1위" }));
    await screen.findByText("뱃지 안내");

    const overlay = document.querySelector('[data-slot="drawer-overlay"]');
    expect(overlay).not.toBeNull();
    await user.click(overlay as Element);

    // jsdom 은 vaul 의 exit 애니메이션(unmount)을 실행하지 못하므로,
    // 닫힘 상태 전환은 Radix 가 즉시 갱신하는 data-state 로 검증한다.
    await waitFor(() =>
      expect(overlay!.getAttribute("data-state")).toBe("closed"),
    );
    expect(onPress).not.toHaveBeenCalled();
  });

  it("카드 본문을 탭하면 onPress가 호출된다", async () => {
    const onPress = vi.fn();
    const user = userEvent.setup();
    render(<TradeCard trade={trade} meta={meta} onPress={onPress} />);

    await user.click(screen.getByText("삼성전자"));

    expect(onPress).toHaveBeenCalledWith(trade);
  });

  it("meta 없이 exchange만 있으면 마켓 뱃지만 렌더한다", () => {
    render(<TradeCard trade={trade} />);

    expect(screen.getByRole("button", { name: "KOSPI" })).toBeDefined();
    expect(screen.queryByText(/시총/)).toBeNull();
    expect(screen.queryByText(/연금/)).toBeNull();
  });
});

describe("TradeCard 표시명(한글 우선)", () => {
  const usTrade: TradeWithAccount = {
    ...trade,
    ticker_symbol: "AAPL",
    asset_name: "Apple Inc.",
    country_code: "US",
    exchange: "NASDAQ",
  };

  it("name_ko가 있으면 한글명을 표시한다", () => {
    render(<TradeCard trade={{ ...usTrade, name_ko: "애플" }} onPress={vi.fn()} />);
    expect(screen.getByText("애플")).toBeDefined();
    expect(screen.queryByText("Apple Inc.")).toBeNull();
  });

  it("name_ko가 없으면 영문 asset_name으로 fallback한다", () => {
    render(<TradeCard trade={usTrade} onPress={vi.fn()} />);
    expect(screen.getByText("Apple Inc.")).toBeDefined();
  });
});
