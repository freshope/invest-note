import { describe, expect, it } from "vitest";
import { normalizePortfolioSummary } from "../usePortfolioSummary";
import type { PortfolioSummaryResponse } from "@/lib/api-client";
import type { Position } from "@/lib/portfolio";

// 구 BE(/portfolio/summary, 해외주식 배포 이전) position — currency/avgBuyPriceNative/
// costBasisNative/evaluationNative 가 없다. 버전 스큐(신 FE + 구 BE)에서 이 shape 가
// 그대로 들어온다. 과거 사고: 가드 없는 신규 필드 소비 → isForeign 오판정 →
// formatMoney(undefined) TypeError → 홈 크래시.
function oldBePosition(overrides: Partial<Position> = {}): Position {
  return {
    key: "005930:KR",
    ticker: "005930",
    country: "KR",
    assetName: "삼성전자",
    exchange: "KOSPI",
    holdingQuantity: 10,
    avgBuyPrice: 70000,
    costBasis: 700000,
    realizedPnL: 0,
    currentPrice: 75000,
    evaluation: 750000,
    unrealizedPnL: 50000,
    lastNote: null,
    lastTradedAt: "2026-06-01T00:00:00+09:00",
    accountIds: ["a1"],
    ...overrides,
  } as Position; // 신규 필드(currency 등) 의도적 누락 — 구 BE shape
}

function summaryWith(positions: Position[]): PortfolioSummaryResponse {
  return {
    totals: {
      totalEvaluation: 0,
      totalUnrealizedPnL: 0,
      totalRealizedPnL: 0,
      totalCash: 0,
      totalAssets: 0,
      monthRealizedPnL: 0,
      monthTradeCount: 0,
      missingQuoteTickers: [],
    },
    positions,
    snapshots: [],
    hasAccounts: true,
    hasTrades: true,
  } as PortfolioSummaryResponse;
}

describe("normalizePortfolioSummary — 버전 스큐(신 FE + 구 BE) 가드", () => {
  it("구 BE shape: KR 포지션의 currency 가 KRW 로 채워져 isForeign 오판정이 없다", () => {
    const out = normalizePortfolioSummary(summaryWith([oldBePosition()]));
    const p = out.positions[0];
    expect(p.currency).toBe("KRW");
    expect(p.avgBuyPriceNative).toBe(70000); // ← formatMoney(undefined) 크래시 방지
    expect(p.costBasisNative).toBe(700000);
    expect(p.evaluationNative).toBe(750000);
  });

  it("구 BE shape: US 포지션도 country 로 currency 를 유도한다", () => {
    const out = normalizePortfolioSummary(
      summaryWith([oldBePosition({ key: "AAPL:US", ticker: "AAPL", country: "US" })]),
    );
    expect(out.positions[0].currency).toBe("USD");
  });

  it("신 BE shape: 기존 값을 덮어쓰지 않는다", () => {
    const out = normalizePortfolioSummary(
      summaryWith([
        oldBePosition({
          key: "AAPL:US",
          country: "US",
          currency: "USD",
          avgBuyPrice: 910000,
          avgBuyPriceNative: 700,
          costBasis: 9100000,
          costBasisNative: 7000,
          evaluation: null,
          evaluationNative: 7500,
        }),
      ]),
    );
    const p = out.positions[0];
    expect(p.avgBuyPriceNative).toBe(700);
    expect(p.costBasisNative).toBe(7000);
    expect(p.evaluationNative).toBe(7500); // evaluation null 이어도 native 유지
  });

  it("positions 누락(방어) 시 빈 배열로 정규화한다", () => {
    const out = normalizePortfolioSummary(
      summaryWith(undefined as unknown as Position[]),
    );
    expect(out.positions).toEqual([]);
  });
});
