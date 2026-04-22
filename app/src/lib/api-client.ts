import type {
  Account,
  TradeType,
  MarketType,
  StrategyType,
  ReasoningTag,
  EmotionType,
  TradeResult,
} from "@/types/database";
import type { StrategyEvaluation } from "@/lib/analysis/strategy-adherence";
import type { SellBreakdown } from "@/lib/holdings";
import type { TradeWithAccount } from "@/lib/trade-utils";

export interface TradeSummary {
  pnl: number;
  result: TradeResult;
  holdingDays: number | null;
  strategyEvaluation: StrategyEvaluation | null;
  breakdown: SellBreakdown;
}

// ============================================================
// 공통 유틸
// ============================================================

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  // 204 No Content는 본문 없음 — json() 호출 시 파싱 오류 발생
  if (res.status === 204) {
    if (!res.ok) throw new Error(`API 오류 (${res.status})`);
    return undefined as T;
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as { error?: string }).error ?? `API 오류 (${res.status})`);
  }
  return data as T;
}

// ============================================================
// Accounts
// ============================================================

export interface AccountInput {
  name: string;
  broker?: string | null;
  cash_balance?: number;
}

export const accountsApi = {
  list: () => apiFetch<Account[]>("/api/accounts"),

  create: (input: AccountInput) =>
    apiFetch<Account>("/api/accounts", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  update: (id: string, input: AccountInput) =>
    apiFetch<Account>(`/api/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  delete: (id: string) =>
    apiFetch<void>(`/api/accounts/${id}`, { method: "DELETE" }),

  tradeCount: (id: string) =>
    apiFetch<{ count: number }>(`/api/accounts/${id}/trade-count`),
};

// ============================================================
// Trades
// ============================================================

export interface TradeCreateInput {
  trade_type: TradeType;
  market_type: MarketType;
  account_id: string;
  asset_name: string;
  ticker_symbol: string;
  country_code?: string;
  exchange?: string; // optional: server default("") fills absent value
  price: number;
  quantity: number;
  commission?: number;
  tax?: number;
  traded_at: string;
}

export interface TradeMetaInput {
  strategy_type?: StrategyType | null;
  emotion?: EmotionType | null;
  reasoning_tags?: ReasoningTag[];
  buy_reason?: string | null;
  sell_reason?: string | null;
  result?: TradeResult | null;
  profit_loss?: number | null;
  reflection_note?: string | null;
  improvement_note?: string | null;
}

export type TradePatchInput = Partial<TradeCreateInput & TradeMetaInput>;

export interface TradesListResponse {
  trades: TradeWithAccount[];
  accounts: Account[];
}

export const tradesApi = {
  list: (params?: { ticker?: string; country?: string }) => {
    const query = params
      ? "?" + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params).filter(([, v]) => v != null) as [string, string][]
          )
        )
      : "";
    return apiFetch<TradesListResponse>(`/api/trades${query}`);
  },

  get: (id: string) => apiFetch<TradeWithAccount>(`/api/trades/${id}`),

  create: (input: TradeCreateInput) =>
    apiFetch<{ id: string; trade_type: TradeType }>("/api/trades", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  update: (id: string, patch: TradePatchInput) =>
    apiFetch<void>(`/api/trades/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  delete: (id: string) =>
    apiFetch<void>(`/api/trades/${id}`, { method: "DELETE" }),

  summary: (id: string) => apiFetch<TradeSummary>(`/api/trades/${id}/summary`),
};

