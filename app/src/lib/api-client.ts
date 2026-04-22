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
import type { Period } from "@/lib/analysis/period";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";
import type { BehaviorProfile, ProfileInputRates } from "@/lib/analysis/profile";
import type { ConcentrationData } from "@/lib/analysis/concentration";
import type { Suggestion } from "@/lib/analysis/rules";
import type { DashboardTotals, Position, AccountSnapshot } from "@/lib/portfolio";
import { createClient } from "@/lib/supabase/client";

// ============================================================
// 공통 유틸
// ============================================================

// NEXT_PUBLIC_API_BASE_URL이 설정돼 있으면 FastAPI origin으로,
// 비어있으면 상대경로(Next.js /api/*) 그대로 사용 — 롤백 스위치.
// FastAPI는 Bearer 토큰 검증, Next.js 라우트는 쿠키 세션을 사용하므로
// API_BASE가 없을 때는 Bearer 헤더를 첨부하지 않는다.
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

// 지연 초기화 싱글턴 — SSR import 시 createBrowserClient 실행을 피하기 위해
// 첫 실제 호출(클라이언트 측) 시점까지 초기화를 미룬다.
let _supabase: ReturnType<typeof createClient> | undefined;
function getSupabase() {
  if (!_supabase) _supabase = createClient();
  return _supabase;
}

async function getBearerHeader(): Promise<Record<string, string>> {
  if (!API_BASE) return {};
  const { data: { session } } = await getSupabase().auth.getSession();
  if (!session?.access_token) return {};
  return { Authorization: `Bearer ${session.access_token}` };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const bearer = await getBearerHeader();
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...bearer, ...(init?.headers ?? {}) },
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

export interface TradeSummary {
  pnl: number;
  result: TradeResult;
  holdingDays: number | null;
  strategyEvaluation: StrategyEvaluation | null;
  breakdown: SellBreakdown;
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

// ============================================================
// Portfolio
// ============================================================

export interface PortfolioSummaryResponse {
  totals: DashboardTotals;
  positions: Position[];
  snapshots: AccountSnapshot[];
  hasAccounts: boolean;
  hasTrades: boolean;
}

export interface PortfolioHoldingParams {
  accountId: string;
  assetName: string;
  ticker?: string | null;
  country: string;
}

export interface PortfolioHoldingResponse {
  quantity: number;
  avgBuyPrice: number | null;
}

export const portfolioApi = {
  summary: () => apiFetch<PortfolioSummaryResponse>("/api/portfolio/summary"),

  holding: (params: PortfolioHoldingParams) => {
    const entries: Record<string, string> = {
      accountId: params.accountId,
      assetName: params.assetName,
      country: params.country,
    };
    if (params.ticker) entries.ticker = params.ticker;
    return apiFetch<PortfolioHoldingResponse>(
      `/api/portfolio/holding?${new URLSearchParams(entries)}`
    );
  },
};

// ============================================================
// Stocks
// ============================================================

export interface StockSearchResult {
  symbol: string;
  code: string;
  name: string;
  market: "KR" | "US" | "OTHER";
  exchange: string;
}

export const stocksApi = {
  search: (q: string) =>
    apiFetch<StockSearchResult[]>(`/api/stocks/search?q=${encodeURIComponent(q)}`),

  quote: (symbols: string) =>
    apiFetch<Record<string, { price: number; currency: string; as_of: string }>>(
      `/api/stocks/quote?symbols=${encodeURIComponent(symbols)}`
    ),
};

// ============================================================
// Analysis
// ============================================================

export interface BehaviorData {
  period?: Period;
  profile: BehaviorProfile;
  inputRates: ProfileInputRates;
  holdingPeriodDist: { bucket: string; count: number }[];
  positionSizeDist: { bucket: string; count: number }[];
  concentration: ConcentrationData;
}

export interface SuggestionsData {
  period?: Period;
  suggestions: Suggestion[];
}

export const analysisApi = {
  summary: (period: Period) =>
    apiFetch<AnalysisSummary>(`/api/analysis/summary?period=${period}`),

  behavior: (period: Period) =>
    apiFetch<BehaviorData>(`/api/analysis/behavior?period=${period}`),

  suggestions: (period: Period) =>
    apiFetch<SuggestionsData>(`/api/analysis/suggestions?period=${period}`),
};
