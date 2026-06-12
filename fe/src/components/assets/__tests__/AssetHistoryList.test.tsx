// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AssetHistoryList } from "../AssetHistoryList";
import type { AssetHistoryItem } from "@/lib/api-client";

afterEach(() => cleanup());

describe("AssetHistoryList — 종목뷰 종가 통화", () => {
  it("closeCurrency=USD 면 종가를 $ 로 표기한다(KRW 자산 열과 혼동 방지)", () => {
    const items: AssetHistoryItem[] = [
      { date: "2026-06-10", value: 217_000, change: 1_000, close: 150.5, qty: 1 },
    ];
    render(<AssetHistoryList items={items} isStockView closeCurrency="USD" />);
    // native USD close 는 $ + 소수 2자리(원으로 오표기/센트 버림 방지).
    expect(screen.getByText("$150.50")).toBeDefined();
  });

  it("closeCurrency 미지정(KR)이면 종가를 원화 정수(₩ 기호 없음)로 표기한다", () => {
    const items: AssetHistoryItem[] = [
      { date: "2026-06-10", value: 100, change: 0, close: 70_000, qty: 1 },
    ];
    render(<AssetHistoryList items={items} isStockView />);
    expect(screen.getByText("70,000")).toBeDefined();
  });
});
