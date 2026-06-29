// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HoldingCard } from "../HoldingCard";
import type { Position } from "@/lib/portfolio";

const usPosition: Position = {
  key: "AAPL:US",
  ticker: "AAPL",
  country: "US",
  currency: "USD",
  assetName: "Apple Inc.",
  exchange: "NASDAQ",
  holdingQuantity: 10,
  avgBuyPrice: 130000,
  avgBuyPriceNative: 100,
  costBasis: 1300000,
  costBasisNative: 1000,
  realizedPnL: 0,
  currentPrice: null,
  evaluation: null,
  evaluationNative: null,
  unrealizedPnL: null,
  lastNote: null,
  lastTradedAt: "2026-06-01T00:00:00Z",
  accountIds: ["a1"],
};

afterEach(cleanup);

describe("HoldingCard 표시명(한글 우선)", () => {
  it("nameKo가 있으면 한글명을 표시한다", () => {
    render(<HoldingCard position={{ ...usPosition, nameKo: "애플" }} onPress={vi.fn()} />);
    expect(screen.getByText("애플")).toBeDefined();
    expect(screen.queryByText("Apple Inc.")).toBeNull();
  });

  it("nameKo가 없으면 영문 assetName으로 fallback한다", () => {
    render(<HoldingCard position={usPosition} onPress={vi.fn()} />);
    expect(screen.getByText("Apple Inc.")).toBeDefined();
  });
});
