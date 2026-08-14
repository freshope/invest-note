// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AllocationTabs } from "../AllocationTabs";
import type { Position } from "@/lib/portfolio";

const heldPosition: Position = {
  key: "005930:KR",
  ticker: "005930",
  country: "KR",
  currency: "KRW",
  assetName: "삼성전자",
  exchange: "KOSPI",
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
  lastTradedAt: "2026-08-01T00:00:00Z",
  accountIds: ["a1"],
};

afterEach(cleanup);

describe("AllocationTabs 빈 상태 문구", () => {
  it("보유 종목이 없으면 전량 매도 상태임을 알린다", () => {
    render(<AllocationTabs positions={[]} snapshots={[]} />);
    expect(screen.getAllByText("보유 중인 종목이 없어요").length).toBeGreaterThan(0);
  });

  it("보유는 있는데 시세가 아직 없으면 조회 중임을 알린다", () => {
    render(<AllocationTabs positions={[heldPosition]} snapshots={[]} />);
    expect(screen.getAllByText("시세를 불러오는 중이에요").length).toBeGreaterThan(0);
  });

  it("보유는 있는데 시세 조회가 실패하면 실패를 알린다", () => {
    render(<AllocationTabs positions={[heldPosition]} snapshots={[]} quotesError />);
    expect(screen.getAllByText("시세를 불러오지 못했어요").length).toBeGreaterThan(0);
  });

  it("시세는 왔는데 평가액이 없으면(환율 미상) 조회 중 문구로 남지 않는다", () => {
    const usPosition: Position = {
      ...heldPosition,
      key: "AAPL:US",
      ticker: "AAPL",
      country: "US",
      currency: "USD",
      assetName: "Apple Inc.",
      currentPrice: 200,
      evaluation: null,
    };
    render(<AllocationTabs positions={[usPosition]} snapshots={[]} />);
    expect(screen.getAllByText("평가금액을 계산할 수 없어요").length).toBeGreaterThan(0);
    expect(screen.queryByText("시세를 불러오는 중이에요")).toBeNull();
  });
});
