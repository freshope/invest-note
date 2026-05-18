import { describe, it, expect } from "vitest";
import { buildPositions } from "../portfolio";
import type { Trade } from "@/types/database";

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
