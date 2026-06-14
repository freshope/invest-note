// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TradeEditPanel } from "../TradeEditPanel";
import { tradesApi } from "@/lib/api-client";
import type { Account, Trade } from "@/types/database";

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    tradesApi: { ...actual.tradesApi, update: vi.fn().mockResolvedValue(undefined) },
    // useFxRate(enabled) 가 US 거래 테스트마다 실 fetch + supabase getSession 을 시도하지 않도록
    // 성공값으로 mock(수정 3 의 null→throw 정책과 충돌 방지).
    stocksApi: {
      ...actual.stocksApi,
      fx: vi.fn().mockResolvedValue({ base: "USD", quote: "KRW", rate: 1350, as_of: "2026-06-09T00:00:00Z" }),
    },
  };
});

const accounts: Account[] = [
  {
    id: "account-1",
    user_id: "user-1",
    name: "테스트 계좌",
    broker: null,
    cash_balance: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function makeTrade(overrides: Partial<Trade>): Trade {
  return {
    id: "trade-1",
    user_id: "user-1",
    account_id: "account-1",
    asset_name: "Apple",
    ticker_symbol: "AAPL",
    market_type: "STOCK",
    trade_type: "BUY",
    price: 100,
    quantity: 10,
    total_amount: 1000,
    traded_at: "2026-01-02T00:00:00Z",
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
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

function renderPanel(trade: Trade) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TradeEditPanel open trade={trade} accounts={accounts} onOpenChange={vi.fn()} onSaved={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("TradeEditPanel — 해외(US) 환율 인지", () => {
  beforeEach(() => {
    (tradesApi.update as ReturnType<typeof vi.fn>).mockClear();
  });
  afterEach(() => cleanup());

  it("US 거래는 체결 원화 입력칸을 노출하고 기존 KRW 원금(price×qty×exchange_rate)으로 초기화한다", () => {
    // 100 USD × 10주 × 1350 = 1,350,000원
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350 }));

    const amountInput = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    expect(amountInput.value).toBe("1,350,000");
    expect(screen.getByText(/가격 \(USD\)/)).toBeDefined();
  });

  it("US 거래 체결 원화를 수정하지 않으면 exchange_rate 를 patch 에서 제외한다(기록 환율 보존)", async () => {
    // 자동 제안값(반올림)을 그대로 두고 제출하면 역산 환율이 기록 환율과 미세하게 어긋난다.
    // exchange_rate(PNL 영향 필드)를 그 drift 값으로 전송하면 의도치 않은 group PnL 재계산이
    // 발생하므로, 미수정 시 patch 에서 제외해 BE 가 기존 환율을 유지하게 한다.
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350 }));

    fireEvent.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(tradesApi.update).toHaveBeenCalled());
    const [, patch] = (tradesApi.update as ReturnType<typeof vi.fn>).mock.calls[0];
    expect("exchange_rate" in patch).toBe(false);
  });

  it("체결 원화 = 가격×수량(역산 환율 1.0)이면 검증 에러로 제출을 막는다", async () => {
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350, price: 100, quantity: 10 }));

    const amountInput = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    // 100 × 10 = 1,000 → 역산 환율 1.0 → BE 가 해외 거래로 거부(400). FE 가 사전 차단.
    fireEvent.change(amountInput, { target: { value: "1000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(screen.getByText(/환율이 1이 되어/)).toBeDefined());
    expect(tradesApi.update).not.toHaveBeenCalled();
  });

  it("US 거래 체결 원화를 수정하면 역산 환율도 반영된다", async () => {
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350 }));

    const amountInput = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    // 1,300,000 / 1000 = 1300
    fireEvent.change(amountInput, { target: { value: "1300000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(tradesApi.update).toHaveBeenCalled());
    const [, patch] = (tradesApi.update as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(patch.exchange_rate).toBeCloseTo(1300, 6);
  });

  it("가격 수정 시 체결 원화는 거래 시점 환율(시세 아님)로 재제안되어 기록 환율이 보존된다", async () => {
    // 가격 100→200, 체결 원화를 직접 건드리지 않으면 anchor=trade.exchange_rate(1350)로 재제안.
    // 200 × 10 × 1350 = 2,700,000 → 역산 환율 2,700,000 / 2000 = 1350 (오타 정정해도 기록 환율 불변).
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350, price: 100, quantity: 10 }));

    // 가격 input 은 라벨이 연결돼 있지 않으므로 초깃값(100)으로 식별. 체결 원화 input 은 제외(라벨로 별도 접근).
    const amountInputEl = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    const priceInput = (screen.getAllByRole("textbox") as HTMLInputElement[]).find(
      (el) => el !== amountInputEl && el.value === "100",
    )!;
    fireEvent.change(priceInput, { target: { value: "200" } });

    const amountInput = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    expect(amountInput.value).toBe("2,700,000");

    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(tradesApi.update).toHaveBeenCalled());
    const [, patch] = (tradesApi.update as ReturnType<typeof vi.fn>).mock.calls[0];
    // 가격만 수정하고 체결 원화는 직접 건드리지 않았으므로 exchange_rate 미전송 → BE 가 기록 환율 유지.
    expect("exchange_rate" in patch).toBe(false);
  });

  it("US 가격에 소수점 입력(716.07)이 보존되어 제출값(역산 환율)에 반영된다", async () => {
    // 가격 100→716.07, 수량 10. 체결 원화는 anchor(1350) 재제안: round(716.07×10×1350)=9,666,945
    // 역산 환율 = 9,666,945 / (716.07×10) = 1350 (round 오차 미세). 핵심은 소수점이 매 키마다 지워지지 않는 것.
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350, price: 100, quantity: 10 }));

    const amountInputEl = screen.getByLabelText(/체결 원화/) as HTMLInputElement;
    const priceInput = (screen.getAllByRole("textbox") as HTMLInputElement[]).find(
      (el) => el !== amountInputEl && el.value === "100",
    )!;
    fireEvent.change(priceInput, { target: { value: "716.07" } });
    // 소수점 입력이 제어 왕복에 의해 제거되지 않고 그대로 보존된다.
    expect(priceInput.value).toBe("716.07");

    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(tradesApi.update).toHaveBeenCalled());
    const [, patch] = (tradesApi.update as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(patch.price).toBeCloseTo(716.07, 6);
    // 체결 원화 미수정 → exchange_rate 미전송(기록 환율 유지). 이 테스트의 핵심은 소수점 보존.
    expect("exchange_rate" in patch).toBe(false);
  });

  it("US 거래는 현재 시세 환율 힌트를 렌더한다", async () => {
    renderPanel(makeTrade({ country_code: "US", exchange_rate: 1350 }));
    await waitFor(() => expect(screen.getByText(/현재 시세/)).toBeDefined());
  });

  it("KR 거래는 체결 원화 입력칸이 없고 exchange_rate 를 patch 에서 제외한다", async () => {
    renderPanel(makeTrade({ country_code: "KR", exchange_rate: 1 }));

    expect(screen.queryByLabelText(/체결 원화/)).toBeNull();
    expect(screen.getByText(/가격 \(원\)/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(tradesApi.update).toHaveBeenCalled());
    const [, patch] = (tradesApi.update as ReturnType<typeof vi.fn>).mock.calls[0];
    expect("exchange_rate" in patch).toBe(false);
  });
});
