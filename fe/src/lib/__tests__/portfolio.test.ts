import { describe, it, expect } from "vitest";
import {
  buildPositions,
  mergeQuotes,
  applyQuotesToTotals,
  applyQuotesToSnapshots,
} from "../portfolio";
import type {
  Position,
  AccountSnapshot,
  DashboardTotals,
  QuoteMap,
} from "../portfolio";
import type { Trade, Account } from "@/types/database";

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

// ── 동일 traded_at BUY/SELL 정렬 (BE sort_for_calc 와 동기화) ──────────
// 시각 없는 거래내역서 일괄 등록 시 같은 날 BUY/SELL 모두 KST 09:00 으로 고정되어
// traded_at 만 비교하면 API 응답 순서에 따라 holdingQuantity 가 달라진다.
describe("buildPositions — 동률 traded_at BUY-우선 정렬", () => {
  const SAME_TS = "2025-06-18T00:00:00Z";

  const trio = [
    makeTrade({
      id: "b29", trade_type: "BUY", asset_name: "NHN", ticker_symbol: "NHN",
      quantity: 29, price: 28400, traded_at: SAME_TS,
    }),
    makeTrade({
      id: "b93", trade_type: "BUY", asset_name: "NHN", ticker_symbol: "NHN",
      quantity: 93, price: 28350, traded_at: SAME_TS,
    }),
    makeTrade({
      id: "s61", trade_type: "SELL", asset_name: "NHN", ticker_symbol: "NHN",
      quantity: 61, price: 27550, traded_at: SAME_TS,
      avg_buy_price: 28361.0738,
    }),
  ];
  const sellLater = makeTrade({
    id: "s625", trade_type: "SELL", asset_name: "NHN", ticker_symbol: "NHN",
    quantity: 61, price: 32000, traded_at: "2025-06-25T00:00:00Z",
    avg_buy_price: 28362.6993,
  });

  function* permutations<T>(arr: T[]): Generator<T[]> {
    if (arr.length <= 1) { yield arr; return; }
    for (let i = 0; i < arr.length; i++) {
      const rest = [...arr.slice(0, i), ...arr.slice(i + 1)];
      for (const p of permutations(rest)) yield [arr[i], ...p];
    }
  }

  it("06/18 BUY/SELL 입력 순열에 무관하게 보유 0주", () => {
    for (const p of permutations(trio)) {
      const positions = buildPositions([...p, sellLater]);
      const nhn = positions.find((x) => x.ticker === "NHN");
      expect(nhn, `순열 ${p.map((t) => t.id).join(",")}`).toBeUndefined();
    }
  });
});

// ── 시세 overlay (옵션 B) ────────────────────────────────────────────
// BE lite 응답(withQuotes=false)에 /stocks/quote 시세를 덮어쓰는 순수 함수 검증.

function makePosition(overrides: Partial<Position> & { key: string }): Position {
  return {
    ticker: overrides.key.split(":")[0],
    country: overrides.key.split(":")[1] ?? "KR",
    assetName: overrides.key,
    exchange: "",
    holdingQuantity: 10,
    avgBuyPrice: 70000,
    costBasis: 700000,
    currentPrice: null,
    evaluation: null,
    unrealizedPnL: null,
    lastNote: null,
    lastTradedAt: "2024-01-10T09:00:00+09:00",
    accountIds: ["a1"],
    ...overrides,
  };
}

function makeAccount(id: string, cash: number): Account {
  return {
    id,
    user_id: "u1",
    name: `계좌 ${id}`,
    broker: null,
    cash_balance: cash,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
}

function makeSnapshot(
  account: Account,
  holdings: { key: string; quantity: number }[],
): AccountSnapshot {
  return {
    account,
    stockEvaluation: 0,
    cashBalance: account.cash_balance,
    totalValue: account.cash_balance,
    holdings,
  };
}

const BASE_TOTALS: DashboardTotals = {
  totalEvaluation: 0,
  totalUnrealizedPnL: 0,
  totalRealizedPnL: 12345,
  totalCash: 1_000_000,
  totalAssets: 1_000_000,
  monthRealizedPnL: 678,
  monthTradeCount: 3,
  missingQuoteTickers: ["삼성전자", "NHN"],
};

function quote(price: number): QuoteMap[string] {
  return { price, currency: "KRW", as_of: "2024-01-10T09:00:00+09:00" };
}

describe("mergeQuotes", () => {
  it("(a) 시세 정상 도착 — currentPrice/evaluation/unrealizedPnL 채워짐", () => {
    const positions = [
      makePosition({ key: "005930:KR", holdingQuantity: 10, costBasis: 700000 }),
    ];
    const quotes: QuoteMap = { "005930:KR": quote(80000) };
    const [pos] = mergeQuotes(positions, quotes);
    expect(pos.currentPrice).toBe(80000);
    expect(pos.evaluation).toBe(800000);
    expect(pos.unrealizedPnL).toBe(100000);
  });

  it("(b) 시세 누락(null) — base 값(null) 유지", () => {
    const positions = [makePosition({ key: "005930:KR" })];
    const quotes: QuoteMap = { "005930:KR": null };
    const [pos] = mergeQuotes(positions, quotes);
    expect(pos.currentPrice).toBeNull();
    expect(pos.evaluation).toBeNull();
    expect(pos.unrealizedPnL).toBeNull();
  });

  it("(d) 빈 quotes(로딩) — 모든 시세 의존 필드 null 유지", () => {
    const positions = [
      makePosition({ key: "005930:KR" }),
      makePosition({ key: "NHN:KR" }),
    ];
    const merged = mergeQuotes(positions, {});
    expect(merged.every((p) => p.currentPrice === null)).toBe(true);
  });
});

describe("applyQuotesToTotals", () => {
  it("(a) 시세 의존 필드만 재계산, 비의존 필드는 BE 값 유지", () => {
    const positions = [
      makePosition({ key: "005930:KR", evaluation: 800000, unrealizedPnL: 100000, currentPrice: 80000 }),
      makePosition({ key: "NHN:KR", evaluation: 300000, unrealizedPnL: -20000, currentPrice: 10000 }),
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, positions);
    expect(totals.totalEvaluation).toBe(1_100_000);
    expect(totals.totalUnrealizedPnL).toBe(80000);
    expect(totals.totalAssets).toBe(1_100_000 + BASE_TOTALS.totalCash);
    expect(totals.missingQuoteTickers).toEqual([]);
    // 비의존 필드 — BE 값 그대로
    expect(totals.totalRealizedPnL).toBe(12345);
    expect(totals.totalCash).toBe(1_000_000);
    expect(totals.monthRealizedPnL).toBe(678);
    expect(totals.monthTradeCount).toBe(3);
  });

  it("(b) 일부 시세 누락 — 해당 평가 0, missingQuoteTickers 포함", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 800000, unrealizedPnL: 100000, currentPrice: 80000 }),
      makePosition({ key: "NHN:KR", assetName: "NHN", currentPrice: null }), // 시세 없음
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, positions);
    expect(totals.totalEvaluation).toBe(800000);
    expect(totals.totalUnrealizedPnL).toBe(100000);
    expect(totals.missingQuoteTickers).toEqual(["NHN"]);
  });

  it("(d) 빈 quotes(로딩) — 모든 종목 missing, 평가 0/현금", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자" }),
      makePosition({ key: "NHN:KR", assetName: "NHN" }),
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, mergeQuotes(positions, {}));
    expect(totals.totalEvaluation).toBe(0);
    expect(totals.totalAssets).toBe(BASE_TOTALS.totalCash);
    expect(totals.missingQuoteTickers).toEqual(["삼성전자", "NHN"]);
  });
});

describe("applyQuotesToSnapshots", () => {
  it("(c) 다계좌 동일 종목 — snapshot 별 자기 holdings 수량으로 분배", () => {
    const a1 = makeAccount("a1", 1_000_000);
    const a2 = makeAccount("a2", 500_000);
    const snapshots = [
      makeSnapshot(a1, [{ key: "005930:KR", quantity: 5 }]),
      makeSnapshot(a2, [{ key: "005930:KR", quantity: 3 }]),
    ];
    const quotes: QuoteMap = { "005930:KR": quote(80000) };
    const [s1, s2] = applyQuotesToSnapshots(snapshots, quotes);
    // 같은 종목이라도 계좌별 자기 수량만 — positions 합산(8)과 구분
    expect(s1.stockEvaluation).toBe(5 * 80000);
    expect(s1.totalValue).toBe(5 * 80000 + 1_000_000);
    expect(s2.stockEvaluation).toBe(3 * 80000);
    expect(s2.totalValue).toBe(3 * 80000 + 500_000);
  });

  it("(b) 시세 없는 key 는 0, 나머지만 합산", () => {
    const a1 = makeAccount("a1", 1_000_000);
    const snapshots = [
      makeSnapshot(a1, [
        { key: "005930:KR", quantity: 10 },
        { key: "NHN:KR", quantity: 20 },
      ]),
    ];
    const quotes: QuoteMap = { "005930:KR": quote(80000), "NHN:KR": null };
    const [s1] = applyQuotesToSnapshots(snapshots, quotes);
    expect(s1.stockEvaluation).toBe(10 * 80000);
    expect(s1.totalValue).toBe(10 * 80000 + 1_000_000);
  });

  it("(d) 빈 quotes(로딩) — stockEvaluation 0, totalValue=현금", () => {
    const a1 = makeAccount("a1", 1_000_000);
    const snapshots = [makeSnapshot(a1, [{ key: "005930:KR", quantity: 10 }])];
    const [s1] = applyQuotesToSnapshots(snapshots, {});
    expect(s1.stockEvaluation).toBe(0);
    expect(s1.totalValue).toBe(1_000_000);
  });

  it("account/cashBalance/holdings 는 그대로 유지", () => {
    const a1 = makeAccount("a1", 1_000_000);
    const holdings = [{ key: "005930:KR", quantity: 10 }];
    const snapshots = [makeSnapshot(a1, holdings)];
    const [s1] = applyQuotesToSnapshots(snapshots, { "005930:KR": quote(80000) });
    expect(s1.account).toBe(a1);
    expect(s1.cashBalance).toBe(1_000_000);
    expect(s1.holdings).toEqual(holdings);
  });

  it("버전 skew — holdings 누락(구 BE 응답)이어도 throw 없이 stockEvaluation=0", () => {
    // 신규 FE 가 holdings additive 필드를 아직 배포 안 한 구 BE 를 호출하면 snapshot.holdings 가
    // undefined 다. 가드 없이 순회하면 TypeError → 홈 렌더 크래시. 가드로 graceful degrade.
    const a1 = makeAccount("a1", 1_000_000);
    const legacySnapshot = {
      account: a1,
      stockEvaluation: 0,
      cashBalance: 1_000_000,
      totalValue: 1_000_000,
    } as unknown as AccountSnapshot; // holdings 의도적 누락
    expect(() =>
      applyQuotesToSnapshots([legacySnapshot], { "005930:KR": quote(80000) }),
    ).not.toThrow();
    const [s1] = applyQuotesToSnapshots([legacySnapshot], {});
    expect(s1.stockEvaluation).toBe(0);
    expect(s1.totalValue).toBe(1_000_000);
  });
});
