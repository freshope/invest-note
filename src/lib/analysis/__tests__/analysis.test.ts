import { describe, it, expect } from "vitest";
import { computeRealizedPnL } from "../realized-pnl";
import { computeHoldingDays } from "../holding-period";
import { computeConcentration } from "../concentration";
import { computeSummary } from "../aggregate";
import { evaluateRules } from "../rules";
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
    reflection_note: null,
    improvement_note: null,
    profit_loss: null,
    country_code: "KR",
    commission: 0,
    tax: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

// ── computeRealizedPnL ──────────────────────────────────────

describe("computeRealizedPnL", () => {
  it("profit_loss 직접 입력값이 있으면 그대로 사용", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", price: 70000, quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 50000, traded_at: "2024-02-01T09:00:00+09:00" }),
    ];
    const map = computeRealizedPnL(trades);
    expect(map.get("s1")).toBe(50000);
  });

  it("WAC fallback: 단순 매수 → 매도", () => {
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

  it("매수 없이 매도 시 avgCost=0으로 처리", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 5, profit_loss: null }),
    ];
    const map = computeRealizedPnL(trades);
    // avgCost = 0/0 = 0 → pnl = 80000*5 - 0 - 0 - 0
    expect(map.get("s1")).toBe(400000);
  });
});

// ── computeHoldingDays ──────────────────────────────────────

describe("computeHoldingDays", () => {
  it("단순 매수 → 매도 보유일 계산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-01-11T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(10); // 10일 보유
  });

  it("부분 매도 FIFO 가중평균 보유일", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY", quantity: 5, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    // b1: 20일 * 5주, b2: 10일 * 5주 → 가중평균 = (20*5 + 10*5) / 10 = 15일
    expect(map.get("s1")).toBe(15);
  });

  it("매수 없이 매도 시 0일 반환", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5 }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(0);
  });

  it("기간 이전 매수를 포함한 FIFO (allTrades 주입 패턴)", () => {
    // 2023년 매수, 2024년 매도 — allTrades로 불러야 올바른 보유일 계산
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", quantity: 10, traded_at: "2023-06-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-01-01T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    // 약 214일 (2023-06-01 → 2024-01-01)
    expect(map.get("s1")).toBeGreaterThan(200);
  });
});

// ── computeConcentration ──────────────────────────────────

describe("computeConcentration", () => {
  const makeTrades = (): Trade[] => [];

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

// ── evaluateRules ──────────────────────────────────────────

describe("evaluateRules", () => {
  const emptyProfile = { tempo: 50, diversification: 50, emotionStability: 50, reasoningQuality: 50, reviewHabit: 50 };
  const emptyConc = { hhi: 0.1, top3: [], byCountry: [], byMarket: [] };

  function makeSummary(overrides = {}) {
    return {
      totalTrades: 20,
      sellTrades: 10,
      winRate: 50,
      totalProfitLoss: 0,
      byStrategy: [],
      byEmotion: [],
      byTag: [],
      missingTagRate: 0,
      feelingRate: 0,
      reflectionRate: 50,
      resultInputRate: 80,
      ...overrides,
    };
  }

  it("매치 조건 미달 시 빈 배열 반환", () => {
    const result = evaluateRules({ summary: makeSummary(), profile: emptyProfile, concentration: emptyConc });
    expect(result).toHaveLength(0);
  });

  it("FOMO 승률 낮으면 emotion_fomo_low_winrate 발동", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "FOMO", count: 8, sellCount: 6, winRate: 30, avgPnL: -5000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_fomo_low_winrate")).toBe(true);
  });

  it("FOMO sellCount < 5이면 발동 안 함 (경계값)", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "FOMO", count: 10, sellCount: 4, winRate: 20, avgPnL: -5000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_fomo_low_winrate")).toBe(false);
  });

  it("concentration_high HHI > 0.5 발동", () => {
    const conc = { ...emptyConc, hhi: 0.6, top3: [{ asset: "삼성전자", weight: 0.6 }] };
    const result = evaluateRules({ summary: makeSummary(), profile: emptyProfile, concentration: conc });
    expect(result.some((r) => r.id === "concentration_high")).toBe(true);
  });

  it("concentration_high HHI <= 0.5, top1 <= 0.4 이면 발동 안 함", () => {
    const conc = { ...emptyConc, hhi: 0.3, top3: [{ asset: "삼성전자", weight: 0.35 }] };
    const result = evaluateRules({ summary: makeSummary(), profile: emptyProfile, concentration: conc });
    expect(result.some((r) => r.id === "concentration_high")).toBe(false);
  });

  it("losing_strategy 승률 < 30%, count >= 5 발동", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SWING", count: 6, winRate: 20, avgPnL: -3000, avgHoldingDays: 14 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    const rule = result.find((r) => r.id === "losing_strategy");
    expect(rule).toBeDefined();
    expect(rule?.severity).toBe("critical");
  });

  it("결과는 critical → warn → info 순으로 정렬", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SWING", count: 6, winRate: 20, avgPnL: -3000, avgHoldingDays: 14 }],
      feelingRate: 50,
      totalTrades: 10,
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    const severities = result.map((r) => r.severity);
    const order = { critical: 0, warn: 1, info: 2 };
    for (let i = 1; i < severities.length; i++) {
      expect(order[severities[i]]).toBeGreaterThanOrEqual(order[severities[i - 1]]);
    }
  });
});
