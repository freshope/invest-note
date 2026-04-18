import { describe, it, expect } from "vitest";
import { computeRealizedPnL, sellPnL } from "../realized-pnl";
import { computeHoldingDays } from "../holding-period";
import { computeConcentration } from "../concentration";
import { computeSummary } from "../aggregate";
import { evaluateRules } from "../rules";
import { parsePeriod, filterByPeriod } from "../period";
import { computeProfile } from "../profile";
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

  it("매수 없이 매도 시 matchedQty=0이므로 pnl=0", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 5, profit_loss: null }),
    ];
    const map = computeRealizedPnL(trades);
    // runningQty=0 → matchedQty=min(5,0)=0 → pnl = 80000*0 - 0*0 - 0 - 0 = 0
    // oversell 없이는 매칭된 수량만 실현손익으로 계산
    expect(map.get("s1")).toBe(0);
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

// ── computeHoldingDays — FIFO multi-sell ─────────────────

describe("computeHoldingDays — FIFO 연속 매도", () => {
  it("분할 매도: 각 매도가 FIFO 순서로 정확한 보유일 계산", () => {
    // b1(5주, 1/1) → b2(5주, 1/11) → s1(5주, 1/21) → s2(5주, 1/21)
    // s1: b1 5주 소비 → (21-1)=20일
    // s2: b2 5주 소비 → (21-11)=10일
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, traded_at: "2024-01-21T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(20); // b1 lot 소비
    expect(map.get("s2")).toBe(10); // b2 lot 소비
  });

  it("매도 수량이 첫 lot을 가로질러 두 lot 소비", () => {
    // b1(3주, 1/1) → b2(7주, 1/11) → s1(10주, 1/21)
    // s1: b1 3주(20일) + b2 7주(10일) → 가중평균 = (3*20 + 7*10)/10 = (60+70)/10 = 13일
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 3, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 7, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 10, traded_at: "2024-01-21T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(13);
  });

  it("큐 소진 후 추가 매수 → 재적립 후 매도", () => {
    // b1(5주) → s1(5주) → b2(5주) → s2(5주)
    // s1은 b1만 소비, s2는 b2만 소비
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  quantity: 5, traded_at: "2024-01-01T09:00:00+09:00" }),
      makeTrade({ id: "s1", trade_type: "SELL", quantity: 5, traded_at: "2024-01-11T09:00:00+09:00" }),
      makeTrade({ id: "b2", trade_type: "BUY",  quantity: 5, traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", quantity: 5, traded_at: "2024-02-11T09:00:00+09:00" }),
    ];
    const map = computeHoldingDays(trades);
    expect(map.get("s1")).toBe(10);
    expect(map.get("s2")).toBe(10);
  });
});

// ── computeSummary ────────────────────────────────────────

describe("computeSummary", () => {
  const emptyMaps = {
    pnlMap: new Map<string, number>(),
    holdingDaysMap: new Map<string, number>(),
  };

  it("거래 없으면 모두 0 반환", () => {
    const s = computeSummary([], emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.totalTrades).toBe(0);
    expect(s.winRate).toBe(0);
    expect(s.totalProfitLoss).toBe(0);
  });

  it("result 입력된 SELL만 winRate 분모 산입", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY" }),
      makeTrade({ id: "s1", trade_type: "SELL", result: "SUCCESS", traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", result: "FAIL",    traded_at: "2024-02-02T09:00:00+09:00" }),
      makeTrade({ id: "s3", trade_type: "SELL", result: null,      traded_at: "2024-02-03T09:00:00+09:00" }), // 제외
    ];
    const s = computeSummary(trades, emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.winRate).toBeCloseTo(50); // 2건 중 1 SUCCESS
    expect(s.resultInputRate).toBeCloseTo(66.67, 1); // 3건 중 2건 입력
  });

  it("totalProfitLoss는 pnlMap 합산", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY" }),
      makeTrade({ id: "s1", trade_type: "SELL", traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", traded_at: "2024-02-02T09:00:00+09:00" }),
    ];
    const pnlMap = new Map([["s1", 30000], ["s2", -10000]]);
    const s = computeSummary(trades, pnlMap, emptyMaps.holdingDaysMap);
    expect(s.totalProfitLoss).toBe(20000);
  });

  it("byEmotion: count=BUY+SELL 합계, winRate=SELL 기준", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY",  emotion: "CALM" }),
      makeTrade({ id: "s1", trade_type: "SELL", emotion: "CALM", result: "SUCCESS", traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", emotion: "CALM", result: "FAIL",    traded_at: "2024-02-02T09:00:00+09:00" }),
    ];
    const s = computeSummary(trades, emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    const calm = s.byEmotion.find((e) => e.type === "CALM");
    expect(calm?.count).toBe(3);        // BUY 1 + SELL 2
    expect(calm?.sellCount).toBe(2);    // SELL만
    expect(calm?.resultCount).toBe(2);  // result 입력된 SELL
    expect(calm?.winRate).toBeCloseTo(50);
  });

  it("byTag: 기간 이전 BUY 태그도 allTrades로 귀속", () => {
    // b1 은 "기간 이전" — allTrades에만 포함
    const allBuy = makeTrade({ id: "b1", trade_type: "BUY", reasoning_tags: ["TECHNICAL"], traded_at: "2023-06-01T09:00:00+09:00" });
    const sell   = makeTrade({ id: "s1", trade_type: "SELL", result: "SUCCESS", traded_at: "2024-01-10T09:00:00+09:00" });
    // period-filtered trades: SELL만 있음 (b1 이전 기간)
    const periodTrades = [sell];
    const allTrades = [allBuy, sell];
    const pnlMap = new Map([["s1", 10000]]);
    const s = computeSummary(periodTrades, pnlMap, emptyMaps.holdingDaysMap, allTrades);
    const techTag = s.byTag.find((t) => t.tag === "TECHNICAL");
    expect(techTag).toBeDefined();
    expect(techTag?.winRate).toBe(100);
  });

  it("byTag: allTrades 없으면 기간 내 BUY만 참조 (기존 동작)", () => {
    const sell = makeTrade({ id: "s1", trade_type: "SELL", result: "SUCCESS", traded_at: "2024-01-10T09:00:00+09:00" });
    // 기간 내 BUY 없음 → 태그 귀속 불가
    const s = computeSummary([sell], emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.byTag).toHaveLength(0);
  });

  it("missingTagRate: 태그 없는 BUY 비율", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", reasoning_tags: [] }),
      makeTrade({ id: "b2", trade_type: "BUY", reasoning_tags: [] }),
      makeTrade({ id: "b3", trade_type: "BUY", reasoning_tags: ["TECHNICAL"] }),
    ];
    const s = computeSummary(trades, emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.missingTagRate).toBeCloseTo(66.67, 1);
  });

  it("feelingRate: FEELING 포함 BUY 비율", () => {
    const trades: Trade[] = [
      makeTrade({ id: "b1", trade_type: "BUY", reasoning_tags: ["FEELING"] }),
      makeTrade({ id: "b2", trade_type: "BUY", reasoning_tags: ["FEELING", "TECHNICAL"] }),
      makeTrade({ id: "b3", trade_type: "BUY", reasoning_tags: ["TECHNICAL"] }),
      makeTrade({ id: "b4", trade_type: "BUY", reasoning_tags: [] }),
    ];
    const s = computeSummary(trades, emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.feelingRate).toBeCloseTo(50); // 4건 중 2건
  });

  it("reflectionRate: reflection_note 작성 비율", () => {
    const trades: Trade[] = [
      makeTrade({ id: "s1", trade_type: "SELL", reflection_note: "좋은 타이밍", traded_at: "2024-02-01T09:00:00+09:00" }),
      makeTrade({ id: "s2", trade_type: "SELL", reflection_note: null,          traded_at: "2024-02-02T09:00:00+09:00" }),
      makeTrade({ id: "s3", trade_type: "SELL", reflection_note: "  ",          traded_at: "2024-02-03T09:00:00+09:00" }), // 공백만 → 미작성
    ];
    const s = computeSummary(trades, emptyMaps.pnlMap, emptyMaps.holdingDaysMap);
    expect(s.reflectionRate).toBeCloseTo(33.33, 1);
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
      byEmotion: [{ type: "FOMO", count: 8, sellCount: 6, resultCount: 5, winRate: 30, avgPnL: -5000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_fomo_low_winrate")).toBe(true);
  });

  it("FOMO sellCount < 5이면 발동 안 함 (경계값)", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "FOMO", count: 10, sellCount: 4, resultCount: 4, winRate: 20, avgPnL: -5000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_fomo_low_winrate")).toBe(false);
  });

  it("FOMO resultCount < 3이면 발동 안 함 — 결과 미입력 방어", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "FOMO", count: 8, sellCount: 6, resultCount: 2, winRate: 0, avgPnL: -5000 }],
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

  it("losing_strategy 승률 < 30%, count >= 5, resultCount >= 3 발동", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SWING", count: 6, resultCount: 5, winRate: 20, avgPnL: -3000, avgHoldingDays: 14 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    const rule = result.find((r) => r.id === "losing_strategy");
    expect(rule).toBeDefined();
    expect(rule?.severity).toBe("critical");
  });

  it("losing_strategy: resultCount < 3 이면 발동 안 함 — 결과 미입력 방어", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SWING", count: 6, resultCount: 2, winRate: 0, avgPnL: -3000, avgHoldingDays: 14 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "losing_strategy")).toBe(false);
  });

  it("emotion_calm_high_winrate: CALM sellCount >= 5 && winRate >= 60 발동", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "CALM", count: 7, sellCount: 5, resultCount: 5, winRate: 70, avgPnL: 8000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_calm_high_winrate")).toBe(true);
  });

  it("emotion_calm_high_winrate: sellCount < 5이면 발동 안 함", () => {
    const summary = makeSummary({
      byEmotion: [{ type: "CALM", count: 4, sellCount: 4, resultCount: 4, winRate: 80, avgPnL: 8000 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "emotion_calm_high_winrate")).toBe(false);
  });

  it("no_reflection: reflectionRate < 30 && sellTrades >= 3 발동", () => {
    const summary = makeSummary({ reflectionRate: 20, sellTrades: 5 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "no_reflection")).toBe(true);
  });

  it("no_reflection: sellTrades < 3이면 발동 안 함 (경계값)", () => {
    const summary = makeSummary({ reflectionRate: 0, sellTrades: 2 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "no_reflection")).toBe(false);
  });

  it("feeling_heavy: feelingRate >= 40 && totalTrades >= 5 발동", () => {
    const summary = makeSummary({ feelingRate: 50, totalTrades: 10 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "feeling_heavy")).toBe(true);
  });

  it("feeling_heavy: totalTrades < 5이면 발동 안 함", () => {
    const summary = makeSummary({ feelingRate: 60, totalTrades: 4 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "feeling_heavy")).toBe(false);
  });

  it("tag_missing_rate_high: missingTagRate >= 30 && totalTrades >= 5 발동", () => {
    const summary = makeSummary({ missingTagRate: 40, totalTrades: 8 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "tag_missing_rate_high")).toBe(true);
  });

  it("tag_missing_rate_high: missingTagRate < 30이면 발동 안 함 (경계값)", () => {
    const summary = makeSummary({ missingTagRate: 29, totalTrades: 10 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "tag_missing_rate_high")).toBe(false);
  });

  it("holding_mismatch: SCALPING count >= 3 && avgHoldingDays > 7 발동", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SCALPING", count: 4, resultCount: 3, winRate: 50, avgPnL: 0, avgHoldingDays: 14 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "holding_mismatch")).toBe(true);
  });

  it("holding_mismatch: avgHoldingDays <= 7이면 발동 안 함 (경계값)", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SCALPING", count: 5, resultCount: 4, winRate: 50, avgPnL: 0, avgHoldingDays: 7 }],
    });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "holding_mismatch")).toBe(false);
  });

  it("결과는 critical → warn → info 순으로 정렬", () => {
    const summary = makeSummary({
      byStrategy: [{ type: "SWING", count: 6, resultCount: 5, winRate: 20, avgPnL: -3000, avgHoldingDays: 14 }],
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

  it("result_missing: resultInputRate < 50 && sellTrades >= 3 발동", () => {
    const summary = makeSummary({ resultInputRate: 30, sellTrades: 5 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "result_missing")).toBe(true);
  });

  it("result_missing: sellTrades < 3 이면 발동 안 함", () => {
    const summary = makeSummary({ resultInputRate: 0, sellTrades: 2 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "result_missing")).toBe(false);
  });

  it("high_winrate: winRate >= 65 && sellTrades >= 5 && resultInputRate >= 50 발동", () => {
    const summary = makeSummary({ winRate: 70, sellTrades: 6, resultInputRate: 80 });
    const result = evaluateRules({ summary, profile: emptyProfile, concentration: emptyConc });
    expect(result.some((r) => r.id === "high_winrate")).toBe(true);
  });

  it("high_winrate: concentration 없이도 발동 (summary-only 룰)", () => {
    const summary = makeSummary({ winRate: 70, sellTrades: 6, resultInputRate: 80 });
    const result = evaluateRules({ summary });
    expect(result.some((r) => r.id === "high_winrate")).toBe(true);
  });

  it("concentration_high: concentration 없으면 발동 안 함", () => {
    const result = evaluateRules({ summary: makeSummary() });
    expect(result.some((r) => r.id === "concentration_high")).toBe(false);
  });
});

// ── parsePeriod ────────────────────────────────────────────────

describe("parsePeriod", () => {
  it("유효한 period 값은 그대로 반환", () => {
    expect(parsePeriod("1m")).toBe("1m");
    expect(parsePeriod("3m")).toBe("3m");
    expect(parsePeriod("6m")).toBe("6m");
    expect(parsePeriod("ytd")).toBe("ytd");
    expect(parsePeriod("all")).toBe("all");
  });

  it("잘못된 값은 all로 fallback", () => {
    expect(parsePeriod("invalid")).toBe("all");
    expect(parsePeriod(null)).toBe("all");
    expect(parsePeriod("")).toBe("all");
  });
});

// ── filterByPeriod ─────────────────────────────────────────────

describe("filterByPeriod", () => {
  function makeTradeLite(id: string, traded_at: string): Trade {
    return makeTrade({ id, trade_type: "BUY", traded_at });
  }

  it("all: 모든 거래 반환", () => {
    const trades = [
      makeTradeLite("t1", "2020-01-01T09:00:00+09:00"),
      makeTradeLite("t2", "2024-06-01T09:00:00+09:00"),
    ];
    const result = filterByPeriod(trades, "all");
    expect(result).toHaveLength(2);
  });

  it("3m: 3개월 이전 거래 제외", () => {
    const now = new Date();
    const recentDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000); // 30일 전
    const oldDate = new Date(now.getTime() - 200 * 24 * 60 * 60 * 1000);  // 200일 전
    const recentIso = recentDate.toISOString().replace("Z", "+09:00");
    const oldIso = oldDate.toISOString().replace("Z", "+09:00");

    const trades = [
      makeTradeLite("recent", recentIso),
      makeTradeLite("old", oldIso),
    ];
    const result = filterByPeriod(trades, "3m");
    expect(result.map((t) => t.id)).toContain("recent");
    expect(result.map((t) => t.id)).not.toContain("old");
  });

  it("ytd: 올해 1월 1일 이전 거래 제외", () => {
    const year = new Date().getFullYear();
    const thisYear = `${year}-01-15T09:00:00+09:00`;  // 올해 1월 15일 (과거)
    const lastYear = `${year - 1}-12-31T09:00:00+09:00`;

    const trades = [
      makeTradeLite("this", thisYear),
      makeTradeLite("last", lastYear),
    ];
    const result = filterByPeriod(trades, "ytd");
    expect(result.map((t) => t.id)).toContain("this");
    expect(result.map((t) => t.id)).not.toContain("last");
  });
});

// ── sellPnL ────────────────────────────────────────────────────

describe("sellPnL", () => {
  it("profit_loss 직접 입력값이 있으면 그대로 반환", () => {
    const sell = makeTrade({ id: "s1", trade_type: "SELL", price: 80000, quantity: 10, profit_loss: 50000 });
    expect(sellPnL(sell, 70000)).toBe(50000);
  });

  it("fallback: price * qty - avgCost * qty - commission - tax", () => {
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

// ── computeProfile ────────────────────────────────────────────

describe("computeProfile", () => {
  it("거래 없으면 diversification=50(중립)", () => {
    const { profile } = computeProfile([], 0, new Map());
    expect(profile.diversification).toBe(50);
  });

  it("FOMO 거래만 있으면 emotionStability 낮음", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", emotion: "FOMO" }),
      makeTrade({ id: "b2", trade_type: "BUY", emotion: "FOMO" }),
    ];
    const { profile } = computeProfile(trades, 0, new Map());
    expect(profile.emotionStability).toBe(0);
  });

  it("CALM 거래만 있으면 emotionStability 높음", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", emotion: "CALM" }),
      makeTrade({ id: "b2", trade_type: "BUY", emotion: "CALM" }),
    ];
    const { profile } = computeProfile(trades, 0, new Map());
    expect(profile.emotionStability).toBe(100);
  });

  it("모든 BUY에 FEELING 태그 → reasoningQuality 낮음", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY", reasoning_tags: ["FEELING"] }),
    ];
    const { profile } = computeProfile(trades, 0, new Map());
    expect(profile.reasoningQuality).toBe(0);
  });

  it("SELL에 reflection_note 있으면 reviewHabit 100", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY" }),
      makeTrade({ id: "s1", trade_type: "SELL", reflection_note: "잘했다" }),
    ];
    const { profile } = computeProfile(trades, 0, new Map());
    expect(profile.reviewHabit).toBe(100);
  });

  it("hhi 기반 diversification 계산", () => {
    const trades = [
      makeTrade({ id: "b1", trade_type: "BUY" }),
      makeTrade({ id: "s1", trade_type: "SELL" }),
    ];
    const { profile } = computeProfile(trades, 0.5, new Map());
    // (1 - 0.5) * 100 = 50
    expect(profile.diversification).toBe(50);
  });
});
