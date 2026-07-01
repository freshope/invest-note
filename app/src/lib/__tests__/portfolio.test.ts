import { describe, it, expect } from "vitest";
import {
  mergeQuotes,
  applyQuotesToTotals,
  applyQuotesToSnapshots,
  buildStockAllocation,
} from "../portfolio";
import type {
  Position,
  AccountSnapshot,
  DashboardTotals,
  QuoteMap,
} from "../portfolio";
import type { Account } from "@/types/database";

// ── 시세 overlay (옵션 B) ────────────────────────────────────────────
// BE lite 응답(withQuotes=false)에 /stocks/quote 시세를 덮어쓰는 순수 함수 검증.

function makePosition(overrides: Partial<Position> & { key: string }): Position {
  const country = overrides.country ?? overrides.key.split(":")[1] ?? "KR";
  return {
    ticker: overrides.key.split(":")[0],
    country,
    currency: country === "US" ? "USD" : "KRW",
    assetName: overrides.key,
    exchange: "",
    holdingQuantity: 10,
    avgBuyPrice: 70000,
    avgBuyPriceNative: 70000,
    costBasis: 700000,
    costBasisNative: 700000,
    realizedPnL: 0,
    currentPrice: null,
    evaluation: null,
    evaluationNative: null,
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
    account_number: null,
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

  it("(e) change_pct(snake) → changePct(camel) 매핑 + 값 없으면 null degrade", () => {
    const positions = [
      makePosition({ key: "005930:KR" }),
      makePosition({ key: "NHN:KR" }),
    ];
    const quotes: QuoteMap = {
      "005930:KR": { price: 80000, currency: "KRW", as_of: "", change_pct: -4.04 },
      "NHN:KR": { price: 10000, currency: "KRW", as_of: "" }, // change_pct 결측
    };
    const [samsung, nhn] = mergeQuotes(positions, quotes);
    expect(samsung.changePct).toBe(-4.04);
    expect(nhn.changePct).toBeNull();
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

  it("(e) US evaluation(KRW)을 그대로 합산 — 환산은 merge 단계에서 끝남", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 700000, unrealizedPnL: 0, currentPrice: 70000 }),
      // US 는 mergeQuotes 가 이미 KRW 로 채운 상태(1,500,000)로 가정.
      makePosition({ key: "AAPL:US", country: "US", assetName: "Apple", evaluation: 1_500_000, unrealizedPnL: 300_000, currentPrice: 100 }),
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, positions);
    expect(totals.totalEvaluation).toBe(2_200_000); // 700,000 + 1,500,000
    expect(totals.totalUnrealizedPnL).toBe(300_000);
    expect(totals.missingQuoteTickers).toEqual([]);
  });

  it("(f) US 환율 미상(시세 있음, evaluation null) → 합계서 제외하되 missing 라벨엔 안 넣음", () => {
    // 시세(currentPrice)는 받았고 환율만 없는 경우라 '시세 미조회'가 아니다 — 홈은 fxBasis
    // 자리에 '환율 미상'을 따로 안내하므로 missingQuoteTickers 에 넣으면 오라벨.
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 700000, unrealizedPnL: 0, currentPrice: 70000 }),
      makePosition({ key: "AAPL:US", country: "US", assetName: "Apple", evaluation: null, currentPrice: 100 }),
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, positions);
    expect(totals.totalEvaluation).toBe(700_000);
    expect(totals.missingQuoteTickers).toEqual([]);
  });

  it("(f2) 시세 자체가 없는 포지션(currentPrice null)은 여전히 missing 라벨", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 700000, unrealizedPnL: 0, currentPrice: 70000 }),
      makePosition({ key: "000660:KR", assetName: "SK하이닉스", evaluation: null, currentPrice: null }),
    ];
    const totals = applyQuotesToTotals(BASE_TOTALS, positions);
    expect(totals.totalEvaluation).toBe(700_000);
    expect(totals.missingQuoteTickers).toEqual(["SK하이닉스"]);
  });

  it("(g) mergeQuotes — US 는 현재 환율로 evaluation KRW + native 산출", () => {
    const positions = [
      makePosition({ key: "AAPL:US", country: "US", holdingQuantity: 10, costBasis: 3_000_000, currentPrice: null }),
    ];
    const quotes: QuoteMap = { "AAPL:US": { price: 220, currency: "USD", as_of: "" } };
    const [pos] = mergeQuotes(positions, quotes, 1530);
    expect(pos.evaluation).toBe(3_366_000);     // 220×10×1530
    expect(pos.evaluationNative).toBe(2200);     // 220×10 (USD)
    expect(pos.unrealizedPnL).toBe(366_000);     // 3,366,000 - 3,000,000(KRW 원가)
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

  it("(e) Phase B — KR+US 혼재 계좌, US 는 usdkrw 로 KRW 환산", () => {
    const a1 = makeAccount("a1", 0);
    const snapshots = [
      makeSnapshot(a1, [
        { key: "005930:KR", quantity: 10 },
        { key: "AAPL:US", quantity: 10 },
      ]),
    ];
    const quotes: QuoteMap = { "005930:KR": quote(70000), "AAPL:US": quote(100) };
    const [s1] = applyQuotesToSnapshots(snapshots, quotes, 1500);
    // KR 70,000×10 + US 100×10×1,500 = 700,000 + 1,500,000 = 2,200,000
    expect(s1.stockEvaluation).toBe(2_200_000);
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

describe("buildStockAllocation (종목별 배분 — evaluation 은 이미 KRW)", () => {
  it("evaluation(KRW) 기준 비중·정렬 — US 가 환율 반영돼 올바른 순위", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 700000, currentPrice: 70000 }),
      // US 는 mergeQuotes 가 이미 KRW 환산(1,500,000).
      makePosition({ key: "AAPL:US", country: "US", assetName: "Apple", evaluation: 1_500_000, currentPrice: 100 }),
    ];
    const data = buildStockAllocation(positions, []);
    expect(data[0]).toEqual({ name: "Apple", value: 1_500_000 });
    expect(data[1]).toEqual({ name: "삼성전자", value: 700_000 });
  });

  it("evaluation null(환율/시세 미상) 포지션은 제외", () => {
    const positions = [
      makePosition({ key: "005930:KR", assetName: "삼성전자", evaluation: 700000, currentPrice: 70000 }),
      makePosition({ key: "AAPL:US", country: "US", assetName: "Apple", evaluation: null, currentPrice: 100 }),
    ];
    const data = buildStockAllocation(positions, []);
    expect(data.map((d) => d.name)).toEqual(["삼성전자"]);
  });

  it("현금은 예수금 엔트리로 추가", () => {
    const a1 = makeAccount("a1", 500000);
    const data = buildStockAllocation([], [makeSnapshot(a1, [])]);
    expect(data).toEqual([{ name: "예수금", value: 500000, color: "var(--muted-foreground)" }]);
  });
});
