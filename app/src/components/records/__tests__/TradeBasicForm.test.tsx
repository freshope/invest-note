// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TradeBasicForm } from "../TradeBasicForm";
import { STORAGE_KEYS } from "@/lib/constants/storage";
import type { Account } from "@/types/database";

vi.mock("../StockSearchInput", () => ({
  StockSearchInput: ({
    value,
    onChange,
    onSelect,
  }: {
    value: string;
    onChange: (value: string) => void;
    onSelect: (stock: { name: string; code: string; market: "KR"; exchange: string }) => void;
  }) => (
    <div>
      <input aria-label="stock-search" value={value} onChange={(e) => onChange(e.target.value)} />
      <button
        type="button"
        onClick={() => {
          onChange("삼성전자");
          onSelect({ name: "삼성전자", code: "005930", market: "KR", exchange: "KOSPI" });
        }}
      >
        select-buy-stock
      </button>
    </div>
  ),
}));

vi.mock("../HoldingSelectInput", () => ({
  HoldingSelectInput: ({
    value,
    onChange,
    onSelect,
  }: {
    value: string;
    onChange: (value: string) => void;
    onSelect: (stock: { name: string; code: string; market: "US"; exchange: string }) => void;
  }) => (
    <div>
      <input aria-label="holding-search" value={value} onChange={(e) => onChange(e.target.value)} />
      <button
        type="button"
        onClick={() => {
          onChange("Apple");
          onSelect({ name: "Apple", code: "AAPL", market: "US", exchange: "NASDAQ" });
        }}
      >
        select-sell-holding
      </button>
    </div>
  ),
}));

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

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <TradeBasicForm accounts={accounts} onTradeCreated={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("TradeBasicForm", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("BUY 종목 선택 후 종목명을 수동 수정하면 stale ticker를 초기화한다", () => {
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "select-buy-stock" }));
    expect(screen.getByText("005930")).toBeDefined();

    fireEvent.change(screen.getByLabelText("stock-search"), { target: { value: "삼성전기" } });

    expect(screen.queryByText("005930")).toBeNull();
    expect(screen.getByText("종목 선택 시 자동 입력")).toBeDefined();
  });

  it("localStorage에 유효한 LAST_ACCOUNT_ID가 있으면 마운트 시 해당 계좌가 미리 선택된다", () => {
    localStorage.setItem(STORAGE_KEYS.LAST_ACCOUNT_ID, "account-1");
    renderForm();

    expect(screen.getByText("테스트 계좌")).toBeDefined();
    expect(screen.queryByText("계좌를 선택하세요")).toBeNull();
  });

  it("localStorage의 LAST_ACCOUNT_ID가 현재 accounts에 없으면 미선택 상태로 시작한다", () => {
    localStorage.setItem(STORAGE_KEYS.LAST_ACCOUNT_ID, "non-existent-id");
    renderForm();

    expect(screen.getByText("계좌를 선택하세요")).toBeDefined();
  });

  it("SELL 보유종목 선택 후 종목명을 수동 수정하면 form 값과 ticker를 함께 초기화한다", () => {
    renderForm();

    fireEvent.click(screen.getByRole("tab", { name: "매도" }));
    fireEvent.click(screen.getByRole("button", { name: "select-sell-holding" }));
    expect(screen.getByText("AAPL")).toBeDefined();

    const holdingInput = screen.getByLabelText("holding-search") as HTMLInputElement;
    fireEvent.change(holdingInput, { target: { value: "Apple Inc" } });

    expect(holdingInput.value).toBe("Apple Inc");
    expect(screen.queryByText("AAPL")).toBeNull();
    expect(screen.getByText("종목 선택 시 자동 입력")).toBeDefined();
  });
});
