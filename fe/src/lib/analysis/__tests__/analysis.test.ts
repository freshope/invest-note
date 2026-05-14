import { describe, it, expect } from "vitest";
import { computeRealizedPnL, sellPnL, sortForCalc, computeGroupPnL, validateMutation, buildPnlMap } from "../realized-pnl";
import { computeHoldingDays } from "../holding-period";
import { computeConcentration } from "../concentration";
import type { Trade } from "@/types/database";
import type { Position } from "@/lib/portfolio";

// ── 테스트 픽스처 헬퍼 ──────────────────────────────────────

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

// ── computeRealizedPnL ──────────────────────────────────────

describe("computeRealizedPnL", () => {
  it("profit_loss 저장값은 무시하고 항상 WAC 계산값 사용", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 50000, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // profit_loss 저장값 50000 무시 → WAC: (80000-70000)*10 = 100000
    expect(map.get("s1")).toBe(100000);
  });

  it("WAC: 단순 매수 → 매도", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: null, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // (80000 - 70000) * 10 - 0 - 0 = 100000
    expect(map.get("s1")).toBe(100000);
  });

  it("부분 매도 후 재매도 WAC 연속 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 60000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 70000, quantity: 5, profit_loss: null, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", price: 80000, quantity: 5, profit_loss: null, traded_at: "2024-03-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    expect(map.get("s1")).toBe(50000);  // (70000-60000)*5
    expect(map.get("s2")).toBe(100000); // (80000-60000)*5
  });

  it("매도 수량 > 매수 수량 시 runningCost가 음수로 내려가지 않음", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 50000, quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 60000, quantity: 10, profit_loss: null, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    const pnl = map.get("s1")!;
    // avgCost = 50000, pnl = 60000*10 - 50000*5 (clamp runningCost >= 0)
    // runningQty clamped to 0, runningCost clamped to 0
    expect(Number.isFinite(pnl)).toBe(true);
    expect(pnl).not.toBeNaN();
  });

  it("매수 없이 매도 시 matchedQty=0이므로 pnl=0", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 5, profit_loss: null }),
    ];
    const map = computeRealizedPnL(trades);
    // runningQty=0 → matchedQty=min(5,0)=0 → pnl = 80000*0 - 0*0 - 0 - 0 = 0
    // oversell 없이는 매칭된 수량만 실현손익으로 계산
    expect(map.get("s1")).toBe(0);
  });

  it("멀티 종목: 같은 배열에 두 종목이 섞여 있어도 각자 WAC 독립 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b_ss", trade_type: "BUY", ticker_symbol: "005930", asset_name: "삼성전자", price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b_sk", trade_type: "BUY", ticker_symbol: "000660", asset_name: "SK하이닉스", price: 50000, quantity: 5, traded_at: "2024-01-02T09:00:00+09:00" }),
      makeTrade({ id: "s_ss", trade_type: "SELL", ticker_symbol: "005930", asset_name: "삼성전자", price: 80000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s_sk", trade_type: "SELL", ticker_symbol: "000660", asset_name: "SK하이닉스", price: 60000, quantity: 5, traded_at: "2024-02-02T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // 005930: (80000-70000)*10 = 100000 — SK하이닉스 BUY가 평단에 영향 X
    expect(map.get("s_ss")).toBe(100000);
    // 000660: (60000-50000)*5 = 50000 — 삼성전자 BUY가 평단에 영향 X
    expect(map.get("s_sk")).toBe(50000);
  });

  it("멀티 계좌: 같은 종목이라도 account_id가 다르면 독립 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b_a1", trade_type: "BUY", account_id: "a1", price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b_a2", trade_type: "BUY", account_id: "a2", price: 90000, quantity: 10, traded_at: "2024-01-02T09:00:00+09:00" }),
      makeTrade({ id: "s_a1", trade_type: "SELL", account_id: "a1", price: 80000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // a1만 자기 평단(70000) 사용. a2 BUY(90000)가 평단을 (70000+90000)/2 같은 식으로 흐려놓지 않음
    expect(map.get("s_a1")).toBe(100000);
  });

  it("멀티 country: 같은 ticker라도 country_code가 다르면 독립 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b_kr", trade_type: "BUY", ticker_symbol: "AAPL", country_code: "KR", price: 100, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b_us", trade_type: "BUY", ticker_symbol: "AAPL", country_code: "US", price: 200, quantity: 10, traded_at: "2024-01-02T09:00:00+09:00" }),
      makeTrade({ id: "s_kr", trade_type: "SELL", ticker_symbol: "AAPL", country_code: "KR", price: 150, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // KR 그룹의 평단(100)만 사용 — US BUY(200)가 평단을 끌어올리지 않음
    expect(map.get("s_kr")).toBe(500);
  });

  it("타 그룹 BUY는 본 그룹 oversell을 메우지 않음 (매칭 수량 = 본 그룹 BUY로 한정)", () => {
    const trades: Trade[] = [
      // 005930 BUY 5주만 보유, SK하이닉스(000660)는 충분히 보유
      makeTrade({ id: "b_ss", trade_type: "BUY", ticker_symbol: "005930", asset_name: "삼성전자", price: 50000, quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b_sk", trade_type: "BUY", ticker_symbol: "000660", asset_name: "SK하이닉스", price: 30000, quantity: 100, traded_at: "2024-01-02T09:00:00+09:00" }),
      // 005930 SELL 10주 시도 — 본 그룹 BUY 5주만 매칭, SK 재고는 무관
      makeTrade({ id: "s_ss", trade_type: "SELL", ticker_symbol: "005930", asset_name: "삼성전자", price: 60000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    // matchedQty = min(10, 5) = 5 → pnl = 60000*5 - 50000*5 = 50000
    expect(map.get("s_ss")).toBe(50000);
  });
});

// ── computeHoldingDays ──────────────────────────────────────

describe("computeHoldingDays", () => {
  it("SELL에 저장된 보유일을 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, holding_days: 10, traded_at: "2024-01-11T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(10);
  });

  it("저장값이 없는 SELL은 포함하지 않음", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 5, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.has("s1")).toBe(false);
  });

  it("매수 없이 매도해도 저장값이 없으면 포함하지 않음", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5 }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.has("s1")).toBe(false);
  });

  it("기간 이전 매수 여부와 관계없이 저장된 SELL 보유일만 사용", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 10, traded_at: "2023-06-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, holding_days: 214, traded_at: "2024-01-01T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(214);
  });
});

// ── computeConcentration ──────────────────────────────────

describe("computeConcentration", () => {
  it("보유 종목 없으면 hhi=0, top3=[]", () => {
    const result = computeConcentration([], []);
    expect(result.hhi).toBe(0);
    expect(result.top3).toHaveLength(0);
  });

  it("단일 종목이면 hhi=1.0", () => {
    const positions: Position[] = [
      { key: "005930:KR", assetName: "삼성전자", country: "KR", costBasis: 1000000, evaluation: 1000000, quantity: 10 } as unknown as Position,
    ];
    const result = computeConcentration(positions, []);
    expect(result.hhi).toBeCloseTo(1.0, 2);
  });

  it("균등 2종목이면 hhi=0.5", () => {
    const positions: Position[] = [
      { key: "A:KR", assetName: "A", country: "KR", costBasis: 500000, evaluation: 500000, quantity: 5 } as unknown as Position,
      { key: "B:KR", assetName: "B", country: "KR", costBasis: 500000, evaluation: 500000, quantity: 5 } as unknown as Position,
    ];
    const result = computeConcentration(positions, []);
    expect(result.hhi).toBeCloseTo(0.5, 2);
  });

  it("evaluation 없으면 costBasis로 fallback", () => {
    const positions: Position[] = [
      { key: "A:KR", assetName: "A", country: "KR", costBasis: 600000, evaluation: undefined, quantity: 6 } as unknown as Position,
      { key: "B:KR", assetName: "B", country: "KR", costBasis: 400000, evaluation: undefined, quantity: 4 } as unknown as Position,
    ];
    const result = computeConcentration(positions, []);
    // weights: 0.6, 0.4 → HHI = 0.36 + 0.16 = 0.52
    expect(result.hhi).toBeCloseTo(0.52, 2);
  });
});

// ── computeHoldingDays — stored multi-sell ─────────────────

describe("computeHoldingDays — 저장된 연속 매도", () => {
  it("분할 매도: 각 SELL의 저장 보유일을 그대로 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, holding_days: 20, traded_at: "2024-01-21T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, holding_days: 10, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(20);
    expect(map.get("s2")).toBe(10);
  });

  it("저장된 가중평균 보유일을 그대로 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 3, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 7, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, holding_days: 13, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(13);
  });

  it("저장값이 있는 SELL만 결과에 포함", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, holding_days: 10, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 5, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, traded_at: "2024-02-11T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(10);
    expect(map.has("s2")).toBe(false);
  });
});


// parsePeriod / filterByPeriod 테스트는 period.test.ts로 분리

// ── sellPnL ────────────────────────────────────────────────────

describe("sellPnL", () => {
  it("항상 WAC 계산값 반환 (profit_loss 저장값 무시)", () => {
    const sell = makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 50000 });
    // profit_loss 저장값 50000 무시 → WAC: (80000-70000)*10 = 100000
    expect(sellPnL(sell, 70000)).toBe(100000);
  });

  it("price * qty - avgCost * qty - commission - tax", () => {
    const sell = makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, commission: 500, tax: 200 });
    // 80000*10 - 70000*10 - 500 - 200 = 800000 - 700000 - 700 = 99300
    expect(sellPnL(sell, 70000)).toBe(99300);
  });

  it("costQty 지정 시 수익/비용 모두 costQty 기준으로 계산 (oversell 시 phantom profit 방지)", () => {
    const sell = makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 15, commission: 0, tax: 0 });
    // costQty=10 → 80000*10 - 70000*10 = 800000 - 700000 = 100000 (보유 수량 기준 실현손익)
    expect(sellPnL(sell, 70000, 10)).toBe(100000);
  });
});

// ── sortForCalc ────────────────────────────────────────────────

describe("sortForCalc", () => {
  it("traded_at 오름차순 정렬", () => {
    const trades: Trade[] = [
      makeTrade({ id: "t2", trade_type: "BUY", traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "t1", trade_type: "BUY", traded_at: "2024-01-01T09:00:00+09:00" }),
    ];
    const sorted = sortForCalc(trades);
    expect(sorted[0].id).toBe("t1");
    expect(sorted[1].id).toBe("t2");
  });

  it("같은 날 BUY가 SELL보다 먼저", () => {
    const sameDay = "2024-01-01T09:00:00+09:00";
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", traded_at: sameDay, created_at: "2024-01-01T01:00:00Z" }),
      makeTrade({ id: "b1", trade_type: "BUY",  traded_at: sameDay, created_at: "2024-01-01T02:00:00Z" }),
    ];
    const sorted = sortForCalc(trades);
    expect(sorted[0].id).toBe("b1");
    expect(sorted[1].id).toBe("s1");
  });

  it("같은 날 같은 타입이면 created_at 오름차순", () => {
    const sameDay = "2024-01-01T09:00:00+09:00";
    const trades: Trade[] = [
      makeTrade({ id: "b2", trade_type: "BUY", traded_at: sameDay, created_at: "2024-01-01T02:00:00Z" }),
      makeTrade({ id: "b1", trade_type: "BUY", traded_at: sameDay, created_at: "2024-01-01T01:00:00Z" }),
    ];
    const sorted = sortForCalc(trades);
    expect(sorted[0].id).toBe("b1");
    expect(sorted[1].id).toBe("b2");
  });
});

// ── computeGroupPnL ────────────────────────────────────────────

describe("computeGroupPnL", () => {
  it("단순 매수 → 매도 그룹 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  price: 70000, quantity: 10, strategy_type: "LONG_TERM", traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.profit_loss).toBe(100000);
    expect(result.get("s1")?.avg_buy_price).toBe(70000);
    expect(result.get("s1")?.holding_days).toBe(31);
    expect(result.get("s1")?.strategy_type).toBe("LONG_TERM");
    expect(result.get("s1")?.matched_qty).toBe(10);
    expect(result.get("s1")?.running_qty_after).toBe(0);
  });

  it("평단가가 WAC 기준으로 정확히 반환됨", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  price: 60000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  price: 80000, quantity: 10, traded_at: "2024-01-15T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 90000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    // WAC = (60000*10 + 80000*10) / 20 = 70000
    expect(result.get("s1")?.avg_buy_price).toBe(70000);
  });

  it("전략은 소비된 BUY lot 중 수량이 가장 큰 전략을 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 60000, quantity: 4, strategy_type: "SCALPING", traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", price: 80000, quantity: 6, strategy_type: "SWING", traded_at: "2024-01-02T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 90000, quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.strategy_type).toBe("SWING");
  });

  it("다른 그룹 거래는 계산에 포함하지 않음", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  price: 70000, quantity: 10, ticker_symbol: "005930", asset_name: "삼성전자", account_id: "a1", traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  price: 50000, quantity: 10, ticker_symbol: "000660", asset_name: "SK하이닉스", account_id: "a1", traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, ticker_symbol: "005930", asset_name: "삼성전자", account_id: "a1", traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    // s1 계산 시 b2(SK하이닉스)는 영향 없음 → avgCost=70000
    expect(result.get("s1")?.profit_loss).toBe(100000);
    expect(result.has("b1")).toBe(false); // BUY는 결과에 없음
  });

  it("reasoning_tags / emotion: 가장 최근 소비 BUY 기준", () => {
    const trades: Trade[] = [
      makeTrade({
        id: "b1",
        trade_type: "BUY",
        quantity: 5,
        reasoning_tags: ["FUNDAMENTAL"],
        emotion: "CALM",
        traded_at: "2024-01-01T09:00:00+09:00",
      }),
      makeTrade({
        id: "b2",
        trade_type: "BUY",
        quantity: 5,
        reasoning_tags: ["TECHNICAL", "NEWS"],
        emotion: "CONFIDENT",
        traded_at: "2024-01-05T09:00:00+09:00",
      }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.reasoning_tags).toEqual(["TECHNICAL", "NEWS"]);
    expect(result.get("s1")?.emotion).toBe("CONFIDENT");
  });

  it("부분 매도가 소비한 BUY만 반영 — 첫 SELL은 b1, 두번째 SELL은 b2", () => {
    const trades: Trade[] = [
      makeTrade({
        id: "b1",
        trade_type: "BUY",
        quantity: 5,
        reasoning_tags: ["FUNDAMENTAL"],
        emotion: "CALM",
        traded_at: "2024-01-01T09:00:00+09:00",
      }),
      makeTrade({
        id: "b2",
        trade_type: "BUY",
        quantity: 5,
        reasoning_tags: ["TECHNICAL"],
        emotion: "FOMO",
        traded_at: "2024-01-05T09:00:00+09:00",
      }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, traded_at: "2024-03-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.reasoning_tags).toEqual(["FUNDAMENTAL"]);
    expect(result.get("s1")?.emotion).toBe("CALM");
    expect(result.get("s2")?.reasoning_tags).toEqual(["TECHNICAL"]);
    expect(result.get("s2")?.emotion).toBe("FOMO");
  });

  it("계좌가 다른 거래는 같은 종목이라도 다른 그룹으로 처리", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 10, account_id: "a1", reasoning_tags: ["FUNDAMENTAL"], traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 10, account_id: "a2", reasoning_tags: ["TECHNICAL"], traded_at: "2024-01-02T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, account_id: "a1", traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    // a1 계좌만 계산 — a2의 BUY는 무시되어야 함
    const keyA1 = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, keyA1);
    expect(result.get("s1")?.reasoning_tags).toEqual(["FUNDAMENTAL"]);
  });

  it("부분 소비: SELL이 일부 BUY만 소비하면 그 BUY의 tags만 반영, 다음 SELL은 다음 lot의 tags", () => {
    // BUY1(qty=8, FUNDAMENTAL) → BUY2(qty=2, TECHNICAL) → SELL1(qty=5) → SELL2(qty=5)
    // FIFO: SELL1는 BUY1 5 소비 → tags=BUY1. SELL2는 BUY1 잔여 3 + BUY2 2 소비 → 최신 BUY2 tags 선택
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 8, reasoning_tags: ["FUNDAMENTAL"], emotion: "CALM", traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 2, reasoning_tags: ["TECHNICAL"], emotion: "FOMO", traded_at: "2024-01-10T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, traded_at: "2024-03-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.reasoning_tags).toEqual(["FUNDAMENTAL"]);
    expect(result.get("s1")?.emotion).toBe("CALM");
    expect(result.get("s2")?.reasoning_tags).toEqual(["TECHNICAL"]);
    expect(result.get("s2")?.emotion).toBe("FOMO");
  });

  it("tie-break: traded_at이 같은 두 BUY를 모두 소비하면 created_at 늦은 쪽(order 큰 lot)의 tags 선택", () => {
    // 같은 timeMs → metaFromConsumedLatest는 order가 큰 쪽 선택. order는 sortForCalc(BUY 우선, 같은 type이면 created_at 오름차순) 결과 push 순서
    const sameTradedAt = "2024-01-01T09:00:00+09:00";
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 5, reasoning_tags: ["FUNDAMENTAL"], emotion: "CALM", traded_at: sameTradedAt, created_at: "2024-01-01T01:00:00Z" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 5, reasoning_tags: ["TECHNICAL"], emotion: "CONFIDENT", traded_at: sameTradedAt, created_at: "2024-01-01T02:00:00Z" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.reasoning_tags).toEqual(["TECHNICAL"]);
    expect(result.get("s1")?.emotion).toBe("CONFIDENT");
  });

  it("모든 소비 BUY의 reasoning_tags가 빈 배열이면 SELL.reasoning_tags=[]", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 5, reasoning_tags: [], emotion: null, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 5, reasoning_tags: [], emotion: null, traded_at: "2024-01-05T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    expect(result.get("s1")?.reasoning_tags).toEqual([]);
    expect(result.get("s1")?.emotion).toBeNull();
  });

  it("BUY 없이 SELL만 있으면 consumed=[] → 메타데이터는 모두 비어 있고 matched_qty=0", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, reasoning_tags: ["NEWS"], emotion: "FOMO", traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const key = { ticker: "005930", assetName: "삼성전자", country: "KR", accountId: "a1" };
    const result = computeGroupPnL(trades, key);
    // consumed=[] → metaFromConsumedLatest 빈 lot 분기. SELL 자체의 reasoning_tags/emotion은 무시됨
    expect(result.get("s1")?.reasoning_tags).toEqual([]);
    expect(result.get("s1")?.emotion).toBeNull();
    expect(result.get("s1")?.strategy_type).toBeNull();
    expect(result.get("s1")?.matched_qty).toBe(0);
    expect(result.get("s1")?.holding_days).toBeNull();
  });
});

// ── validateMutation ───────────────────────────────────────────

describe("validateMutation", () => {
  function baseTrades(): Trade[] {
    return [
      makeTrade({ id: "b1", trade_type: "BUY",  price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00", created_at: "2024-01-01T00:00:00Z" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 5,  traded_at: "2024-02-01T09:00:00+09:00", created_at: "2024-02-01T00:00:00Z" }),
      makeTrade({ id: "s2", trade_type: "SELL", price: 90000, quantity: 5,  traded_at: "2024-03-01T09:00:00+09:00", created_at: "2024-03-01T00:00:00Z" }),
    ];
  }

  it("BUY 삭제로 oversell 발생 → ok: false", () => {
    const trades = baseTrades();
    const result = validateMutation(trades, { type: "delete", trade: trades[0] });
    expect(result.ok).toBe(false);
  });

  it("BUY 수량 감소로 이후 SELL oversell → ok: false", () => {
    const trades = baseTrades();
    const result = validateMutation(trades, {
      type: "update",
      trade: trades[0],
      patch: { quantity: 3 }, // 10→3: SELL(5)+(5)=10 > 3 → oversell
    });
    expect(result.ok).toBe(false);
  });

  it("BUY 수량 유지 시 ok: true + newPnL 반환", () => {
    const trades = baseTrades();
    const result = validateMutation(trades, {
      type: "update",
      trade: trades[0],
      patch: { price: 60000 }, // 가격만 변경 → 수량 문제 없음
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.newPnL.has("s1")).toBe(true);
      expect(result.newPnL.has("s2")).toBe(true);
      // avgCost=60000 → s1: (80000-60000)*5=100000
      expect(result.newPnL.get("s1")).toBe(100000);
    }
  });

  it("SELL 삭제는 runningQty 증가 방향 → ok: true", () => {
    const trades = baseTrades();
    const result = validateMutation(trades, { type: "delete", trade: trades[1] }); // s1 삭제
    expect(result.ok).toBe(true);
  });

  it("과거 시점 BUY 삽입 후 이후 SELL oversell 없으면 ok: true", () => {
    const trades = baseTrades();
    const newBuy = makeTrade({ id: "b2", trade_type: "BUY", price: 65000, quantity: 5, traded_at: "2024-01-15T09:00:00+09:00", created_at: "2024-01-15T00:00:00Z" });
    const result = validateMutation(trades, { type: "insert", trade: newBuy });
    expect(result.ok).toBe(true);
  });

  it("같은 날 BUY+SELL 삽입: BUY 먼저 처리되어 oversell 오탐 없음", () => {
    const sameDay = "2024-04-01T09:00:00+09:00";
    const trades: Trade[] = []; // 빈 상태에서 시작
    // BUY 10주 삽입 후 같은 날 SELL 10주 시뮬레이션
    const buy = makeTrade({ id: "b1", trade_type: "BUY",  price: 70000, quantity: 10, traded_at: sameDay, created_at: "2024-04-01T01:00:00Z" });
    const sell = makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, traded_at: sameDay, created_at: "2024-04-01T02:00:00Z" });
    const tradesWithBuy = [buy];
    const result = validateMutation(tradesWithBuy, { type: "insert", trade: sell });
    // BUY가 SELL보다 먼저 처리되어 oversell 없음
    expect(result.ok).toBe(true);
  });
});

// ── buildPnlMap ─────────────────────────────────────────────

describe("buildPnlMap", () => {
  it("SELL의 저장된 profit_loss를 그대로 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 70000, quantity: 10 }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 95000 }),
    ];
    const map = buildPnlMap(trades);
    expect(map.get("s1")).toBe(95000);
    expect(map.has("b1")).toBe(false);
  });

  it("profit_loss가 null이면 0 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY" }),
      makeTrade({ id: "s1", trade_type: "SELL", profit_loss: null }),
    ];
    const map = buildPnlMap(trades);
    expect(map.get("s1")).toBe(0);
  });

  it("여러 SELL 모두 저장값 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 70000, quantity: 20, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 100000, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", price: 75000, quantity: 10, profit_loss: 50000, traded_at: "2024-03-01T09:00:00+09:00" }),
    ];
    const map = buildPnlMap(trades);
    expect(map.get("s1")).toBe(100000);
    expect(map.get("s2")).toBe(50000);
  });
});
