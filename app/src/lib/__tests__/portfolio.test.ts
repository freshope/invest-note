import { describe, it, expect } from "vitest";
import { buildPositions } from "../portfolio";
import type { Trade } from "@/types/database";

function makeTrade(overrides: Partial<Trade> & { id: string; trade_type: Trade["trade_type"] }): Trade {
  return {
    user_id: "u1",
    account_id: "a1",
    asset_name: "삼성전자",
    ticker_symbol: "005930",
    market_type: "STOCK",
    price: 70000,
    quantity: 10,
    total_amount: 700000,
    traded_at: "2024-01-10T09:00:00+09:00",
    strategy_type: null,
    reasoning_tags: [],
    buy_reason: null,
    sell_reason: null,
    emotion: null,
    result: null,
    reflection_note: null,
    improvement_note: null,
    profit_loss: null,
    avg_buy_price: null,
    holding_days: null,
    country_code: "KR",
    exchange: "",
    commission: 0,
    tax: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

// ── exchange="" 가드 로직 ────────────────────────────────────

describe("buildPositions — exchange 가드", () => {
  it("첫 거래가 exchange='' 이면 position.exchange는 빈 문자열", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", exchange: "" }),
    ];
    const [pos] = buildPositions(trades);
    expect(pos.exchange).toBe("");
  });

  it("exchange 있는 BUY 후 exchange='' BUY가 오면 이전 거래소 유지", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", exchange: "KOSPI", traded_at: "2024-01-10T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", exchange: "", traded_at: "2024-01-11T09:00:00+09:00" }),
    ];
    const [pos] = buildPositions(trades);
    expect(pos.exchange).toBe("KOSPI");
  });

  it("나중에 오는 비어있지 않은 exchange로 덮어쓴다", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", exchange: "KOSPI", traded_at: "2024-01-10T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", exchange: "KOSDAQ", traded_at: "2024-01-11T09:00:00+09:00" }),
    ];
    const [pos] = buildPositions(trades);
    expect(pos.exchange).toBe("KOSDAQ");
  });

  it("두 계좌에 같은 종목이 있을 때 비어있지 않은 계좌의 exchange가 포지션에 반영된다", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", account_id: "a1", exchange: "" }),
      makeTrade({ id: "b2", trade_type: "BUY", account_id: "a2", exchange: "NASDAQ" }),
    ];
    const positions = buildPositions(trades);
    expect(positions).toHaveLength(1);
    expect(positions[0].exchange).toBe("NASDAQ");
  });

  it("두 계좌 모두 exchange='' 이면 position.exchange도 빈 문자열", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", account_id: "a1", exchange: "" }),
      makeTrade({ id: "b2", trade_type: "BUY", account_id: "a2", exchange: "" }),
    ];
    const positions = buildPositions(trades);
    expect(positions[0].exchange).toBe("");
  });
});
