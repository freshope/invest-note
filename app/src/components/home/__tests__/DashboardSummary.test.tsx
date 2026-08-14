// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DashboardBody } from "../DashboardSummary";
import type { DashboardTotals } from "@/lib/portfolio";

const totals: DashboardTotals = {
  totalEvaluation: 0,
  totalUnrealizedPnL: 0,
  totalRealizedPnL: 1_876_750,
  totalCash: 0,
  totalAssets: 0,
  monthRealizedPnL: 1_876_750,
  monthTradeCount: 3,
  missingQuoteTickers: [],
};

afterEach(cleanup);

describe("DashboardBody 손익 카드 표기", () => {
  it("백만 단위 손익도 축약 표기해 3열 카드를 넘치지 않는다", () => {
    render(<DashboardBody totals={totals} />);
    expect(screen.getAllByText("+188만원").length).toBe(2);
    expect(screen.queryByText("+1,876,750원")).toBeNull();
  });

  it("1만 미만 소액은 정확한 값을 유지한다", () => {
    render(<DashboardBody totals={{ ...totals, totalUnrealizedPnL: -8_500 }} />);
    expect(screen.getByText("-8,500원")).toBeDefined();
  });
});
