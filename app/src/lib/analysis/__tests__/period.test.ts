import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { filterByPeriod, parsePeriod } from "../period";
import type { Trade } from "@/types/database";

// ── 픽스처 ────────────────────────────────────────────────────

function makeTrade(id: string, traded_at: string): Trade {
  return {
    id,
    user_id: "u1",
    account_id: "a1",
    asset_name: "삼성전자",
    ticker_symbol: "005930",
    market_type: "STOCK",
    trade_type: "BUY",
    price: 70000,
    quantity: 10,
    total_amount: 700000,
    traded_at,
    strategy_type: null,
    reasoning_tags: [],
    custom_tags: [],
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
  };
}

// ── parsePeriod ───────────────────────────────────────────────

describe("parsePeriod", () => {
  it("유효한 5개 값을 그대로 반환", () => {
    expect(parsePeriod("1m")).toBe("1m");
    expect(parsePeriod("3m")).toBe("3m");
    expect(parsePeriod("6m")).toBe("6m");
    expect(parsePeriod("ytd")).toBe("ytd");
    expect(parsePeriod("all")).toBe("all");
  });

  it("null / 빈 문자열 / 알 수 없는 값은 all로 fallback", () => {
    expect(parsePeriod(null)).toBe("all");
    expect(parsePeriod("")).toBe("all");
    expect(parsePeriod("invalid")).toBe("all");
    expect(parsePeriod("12m")).toBe("all");
  });

  it("대소문자가 다르면 fallback (정확 일치만 허용)", () => {
    expect(parsePeriod("YTD")).toBe("all");
    expect(parsePeriod("1M")).toBe("all");
    expect(parsePeriod("All")).toBe("all");
  });
});

// ── filterByPeriod ────────────────────────────────────────────

describe("filterByPeriod", () => {
  // KST 정오로 고정 — KST 자정 경계 검증과 충돌하지 않도록 자정에서 충분히 떨어진 시점
  const NOW_ISO = "2024-06-15T12:00:00+09:00";

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_ISO));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("빈 배열 입력은 빈 배열 반환", () => {
    expect(filterByPeriod([], "all")).toEqual([]);
    expect(filterByPeriod([], "3m")).toEqual([]);
    expect(filterByPeriod([], "ytd")).toEqual([]);
  });

  it("all: 과거/현재 거래 모두 포함, from 제한 없음", () => {
    const trades = [
      makeTrade("ancient", "2010-01-01T09:00:00+09:00"),
      makeTrade("recent", "2024-06-15T11:59:59+09:00"),
    ];
    expect(filterByPeriod(trades, "all").map((t) => t.id)).toEqual(["ancient", "recent"]);
  });

  it("1m: KST 1개월 전 자정 직전 거래는 제외, 자정 정각은 포함", () => {
    const trades = [
      makeTrade("before", "2024-05-14T23:59:59+09:00"),
      makeTrade("boundary", "2024-05-15T00:00:00+09:00"),
      makeTrade("inside", "2024-06-01T09:00:00+09:00"),
    ];
    expect(filterByPeriod(trades, "1m").map((t) => t.id)).toEqual(["boundary", "inside"]);
  });

  it("3m: KST 3개월 전 자정 경계", () => {
    const trades = [
      makeTrade("before", "2024-03-14T23:59:59+09:00"),
      makeTrade("boundary", "2024-03-15T00:00:00+09:00"),
      makeTrade("inside", "2024-04-01T09:00:00+09:00"),
    ];
    expect(filterByPeriod(trades, "3m").map((t) => t.id)).toEqual(["boundary", "inside"]);
  });

  it("6m: KST 6개월 전 자정 경계", () => {
    const trades = [
      makeTrade("before", "2023-12-14T23:59:59+09:00"),
      makeTrade("boundary", "2023-12-15T00:00:00+09:00"),
      makeTrade("inside", "2024-01-01T09:00:00+09:00"),
    ];
    expect(filterByPeriod(trades, "6m").map((t) => t.id)).toEqual(["boundary", "inside"]);
  });

  it("ytd: 올해 KST 1월 1일 자정부터 포함, 작년 말일은 제외", () => {
    const trades = [
      makeTrade("lastYear", "2023-12-31T23:59:59+09:00"),
      makeTrade("firstDay", "2024-01-01T00:00:00+09:00"),
      makeTrade("midYear", "2024-04-15T09:00:00+09:00"),
    ];
    expect(filterByPeriod(trades, "ytd").map((t) => t.id)).toEqual(["firstDay", "midYear"]);
  });

  it("to(now) 시각과 정확히 같은 거래는 포함 (`<=`)", () => {
    const trades = [makeTrade("atNow", NOW_ISO)];
    expect(filterByPeriod(trades, "3m").map((t) => t.id)).toEqual(["atNow"]);
    expect(filterByPeriod(trades, "all").map((t) => t.id)).toEqual(["atNow"]);
  });

  it("미래 거래(now 초과)는 모든 모드에서 제외", () => {
    const trades = [makeTrade("future", "2024-06-15T12:00:01+09:00")];
    expect(filterByPeriod(trades, "all")).toEqual([]);
    expect(filterByPeriod(trades, "3m")).toEqual([]);
    expect(filterByPeriod(trades, "ytd")).toEqual([]);
  });
});
