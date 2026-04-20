import { describe, it, expect } from "vitest";
import { computeFlexibleBreakdown } from "../holdings";
import type { Trade } from "@/types/database";

function makeSell(overrides: Partial<Trade> = {}): Trade {
  return {
    id: "s1",
    user_id: "u1",
    account_id: "a1",
    asset_name: "삼성전자",
    ticker_symbol: "005930",
    market_type: "STOCK",
    trade_type: "SELL",
    price: 80000,
    quantity: 10,
    total_amount: 800000,
    traded_at: "2024-02-01T09:00:00+09:00",
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
    country_code: "KR",
    commission: 0,
    tax: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

// ── computeFlexibleBreakdown ─────────────────────────────────

describe("computeFlexibleBreakdown", () => {
  it("저장된 avg_buy_price / profit_loss로 breakdown 구성", () => {
    const sell = makeSell({ price: 80000, quantity: 10, avg_buy_price: 70000, profit_loss: 100000 });
    const bd = computeFlexibleBreakdown(sell);
    expect(bd.avgCostPrice).toBe(70000);
    expect(bd.pnl).toBe(100000);
    expect(bd.sellAmount).toBe(800000);
    expect(bd.costBasis).toBe(700000);
    expect(bd.quantity).toBe(10);
    expect(bd.isManualInput).toBe(false);
  });

  it("avg_buy_price null이면 avgCostPrice=0", () => {
    const sell = makeSell({ avg_buy_price: null, profit_loss: 0 });
    const bd = computeFlexibleBreakdown(sell);
    expect(bd.avgCostPrice).toBe(0);
    expect(bd.costBasis).toBe(0);
  });

  it("profit_loss null이면 pnl=0", () => {
    const sell = makeSell({ avg_buy_price: 70000, profit_loss: null });
    const bd = computeFlexibleBreakdown(sell);
    expect(bd.pnl).toBe(0);
  });

  it("commission / tax가 breakdown에 반영됨", () => {
    const sell = makeSell({ commission: 1500, tax: 500, avg_buy_price: 70000, profit_loss: 98000 });
    const bd = computeFlexibleBreakdown(sell);
    expect(bd.commission).toBe(1500);
    expect(bd.tax).toBe(500);
    expect(bd.pnl).toBe(98000);
  });
});
