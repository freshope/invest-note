import { describe, expect, it } from "vitest";
import {
  convertAssetSeries,
  convertDailySeries,
  convertInvestedAmount,
  convertItems,
} from "../asset-history-convert";
import type { AssetHistoryItem, AssetHistoryPoint } from "@/lib/api-client";

const SERIES: AssetHistoryPoint[] = [
  { date: "2026-06-01", value: 200 },
  { date: "2026-06-02", value: 210 },
];

// items 는 BE 가 최신 먼저로 내려준다(reverse 후 오름차순).
const ITEMS: AssetHistoryItem[] = [
  { date: "2026-06-02", value: 210, change: 10, close: 210, qty: 1 },
  { date: "2026-06-01", value: 200, change: 0, close: 200, qty: 1 },
];

describe("asset-history-convert — US 종목뷰 KRW 환산", () => {
  it("convertAssetSeries: rate 적용 시 value×rate, date 보존", () => {
    expect(convertAssetSeries(SERIES, 1350)).toEqual([
      { date: "2026-06-01", value: 270000 },
      { date: "2026-06-02", value: 283500 },
    ]);
  });

  it("convertAssetSeries: rate=null 이면 원본 그대로(KR·계좌뷰, USD-as-KRW 방지)", () => {
    expect(convertAssetSeries(SERIES, null)).toBe(SERIES);
  });

  it("convertInvestedAmount: rate 적용 / null·amount null 폴백", () => {
    expect(convertInvestedAmount(2000, 1350)).toBe(2_700_000);
    expect(convertInvestedAmount(2000, null)).toBe(2000);
    expect(convertInvestedAmount(null, 1350)).toBeNull();
  });

  it("convertDailySeries: 최신먼저 items → 오름차순 + change×rate", () => {
    expect(convertDailySeries(ITEMS, 1350)).toEqual([
      { date: "2026-06-01", value: 0 },
      { date: "2026-06-02", value: 13500 },
    ]);
  });

  it("convertDailySeries: rate=null 이면 change 원본(오름차순만)", () => {
    expect(convertDailySeries(ITEMS, null)).toEqual([
      { date: "2026-06-01", value: 0 },
      { date: "2026-06-02", value: 10 },
    ]);
  });

  it("convertItems: value·change 만 환산, close·qty(1주 가격)는 native 유지", () => {
    const out = convertItems(ITEMS, 1350);
    expect(out[0]).toEqual({
      date: "2026-06-02",
      value: 283500,
      change: 13500,
      close: 210, // 종가는 1주당 가격 — 환산 안 함
      qty: 1,
    });
  });

  it("convertItems: rate=null 이면 원본 그대로", () => {
    expect(convertItems(ITEMS, null)).toBe(ITEMS);
  });
});
