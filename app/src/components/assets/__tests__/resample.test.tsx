import { describe, expect, it } from "vitest";
import { resampleAssetHistory, firstBaselineOf } from "../resample";
import type { AssetHistoryItem } from "@/lib/api-client";

// 최신 먼저. change 는 전일대비(첫 항목=oldest 는 value-firstBaseline 로 만들어졌다고 가정).
// firstBaseline = 100 이라고 두고 daily value 시퀀스: 100→110→130→125→140 (월~금 한 주 + 다음 주 월).
function daily(): AssetHistoryItem[] {
  // oldest→newest 로 만든 뒤 reverse(최신 먼저).
  const asc = [
    { date: "2026-06-01", value: 110 }, // 월
    { date: "2026-06-03", value: 130 }, // 수
    { date: "2026-06-05", value: 125 }, // 금 ← 첫 주 마지막 거래일
    { date: "2026-06-08", value: 140 }, // 다음 주 월 ← 둘째 주 마지막
  ];
  const firstBaseline = 100;
  const items = asc.map((p, i) => ({
    date: p.date,
    value: p.value,
    change: p.value - (i === 0 ? firstBaseline : asc[i - 1].value),
  }));
  items.reverse();
  return items;
}

describe("firstBaselineOf", () => {
  it("최신-먼저 items 에서 첫 구간 기준값(매수원금)을 복원한다", () => {
    expect(firstBaselineOf(daily())).toBe(100);
  });
  it("빈 배열은 0", () => {
    expect(firstBaselineOf([])).toBe(0);
  });
});

describe("resampleAssetHistory — 주 단위", () => {
  it("각 주의 마지막 거래일 value 를 대표로 채택한다", () => {
    const weekly = resampleAssetHistory(daily(), "week", 100);
    // 최신 먼저: [2026-06-08(둘째주), 2026-06-05(첫주 마지막)]
    expect(weekly.map((w) => w.date)).toEqual(["2026-06-08", "2026-06-05"]);
    expect(weekly.map((w) => w.value)).toEqual([140, 125]);
  });

  it("change 를 구간 연속 차분으로 재계산한다(첫 구간은 firstBaseline 대비)", () => {
    const weekly = resampleAssetHistory(daily(), "week", 100);
    // 첫 주(2026-06-05): 125 - 100 = 25 / 둘째 주(2026-06-08): 140 - 125 = 15
    const byDate = Object.fromEntries(weekly.map((w) => [w.date, w.change]));
    expect(byDate["2026-06-05"]).toBe(25);
    expect(byDate["2026-06-08"]).toBe(15);
  });
});

describe("resampleAssetHistory — 월 단위", () => {
  it("한 달 안 거래는 마지막 거래일 하나로 접힌다", () => {
    const monthly = resampleAssetHistory(daily(), "month", 100);
    expect(monthly).toHaveLength(1);
    expect(monthly[0].date).toBe("2026-06-08");
    expect(monthly[0].value).toBe(140);
    expect(monthly[0].change).toBe(40); // 140 - 100
  });
});

describe("resampleAssetHistory — 일 단위 / 종목뷰 필드", () => {
  it("일 단위는 입력을 그대로 통과시킨다", () => {
    const items = daily();
    expect(resampleAssetHistory(items, "day", 100)).toBe(items);
  });

  it("대표행의 close/qty(마지막 거래일 값)를 보존한다", () => {
    const items: AssetHistoryItem[] = [
      { date: "2026-06-05", value: 125, change: -5, close: 70_500, qty: 2 }, // 첫 주 마지막
      { date: "2026-06-03", value: 130, change: 20, close: 71_000, qty: 2 },
      { date: "2026-06-01", value: 110, change: 10, close: 69_000, qty: 2 },
    ];
    const weekly = resampleAssetHistory(items, "week", 100);
    expect(weekly).toHaveLength(1);
    expect(weekly[0].close).toBe(70_500); // 마지막 거래일 종가
    expect(weekly[0].qty).toBe(2);
  });
});
