import { describe, it, expect } from "vitest";
import { computeRealizedPnL, sellPnL, sortForCalc, computeGroupPnL, validateMutation, buildPnlMap } from "../realized-pnl";
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

  it("byStrategy와 strategyAdherence는 SELL 계획 전략과 보유일 기준으로 계산", () => {
    const buy = makeTrade({
      id: "b1",
      trade_type: "BUY",
      strategy_type: "LONG_TERM",
      traded_at: "2024-01-01T09:00:00+09:00",
    });
    const sell = makeTrade({
      id: "s1",
      trade_type: "SELL",
      strategy_type: "LONG_TERM",
      result: "SUCCESS",
      traded_at: "2024-01-02T09:00:00+09:00",
    });
    const s = computeSummary([buy, sell], new Map([["s1", 10000]]), new Map([["s1", 1]]));
    expect(s.byStrategy[0].type).toBe("LONG_TERM");
    expect(s.strategyAdherenceRate).toBe(0);
    expect(s.byStrategyAdherence[0].type).toBe("DEVIATED");
    expect(s.byStrategyAdherence[0].winRate).toBe(100);
  });

  it("holding_days가 없어도 byStrategy는 SELL 전략 버킷을 유지", () => {
    const sell = makeTrade({
      id: "s1",
      trade_type: "SELL",
      strategy_type: "SWING",
      result: "SUCCESS",
      traded_at: "2024-01-02T09:00:00+09:00",
    });
    const s = computeSummary([sell], new Map([["s1", 10000]]), emptyMaps.holdingDaysMap);
    expect(s.byStrategy[0].type).toBe("SWING");
    expect(s.byStrategy[0].avgHoldingDays).toBe(0);
    expect(s.strategyAdherenceRate).toBe(0);
  });

  it("strategyAdherence는 SELL에 저장된 전략과 보유일을 사용", () => {
    const buy = makeTrade({
      id: "b1",
      trade_type: "BUY",
      ticker_symbol: "",
      strategy_type: "SWING",
      traded_at: "2024-01-01T09:00:00+09:00",
    });
    const sell = makeTrade({
      id: "s1",
      trade_type: "SELL",
      ticker_symbol: "005930",
      strategy_type: "SWING",
      holding_days: 9,
      result: "SUCCESS",
      traded_at: "2024-01-10T09:00:00+09:00",
    });
    const s = computeSummary([buy, sell], new Map([["s1", 10000]]), emptyMaps.holdingDaysMap);
    expect(s.byStrategy[0].type).toBe("SWING");
    expect(s.byStrategy[0].avgHoldingDays).toBe(9);
    expect(s.strategyAdherenceRate).toBe(100);
    expect(s.byStrategyAdherence[0].type).toBe("FOLLOWED");
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
      strategyAdherenceRate: 0,
      byStrategyAdherence: [],
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
