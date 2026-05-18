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

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// NEXT_PUBLIC_API_BASE_URL: FastAPI 서버 주소. 정적 export 환경에서는 필수.
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

// FastAPI 라우트 매핑 — 인라인 경로 문자열 사용 금지, 반드시 이 객체 경유.
const ROUTES = {
  accounts: {
    base: "/api/accounts",
    byId: (id: string) => `/api/accounts/${id}`,
    tradeCount: (id: string) => `/api/accounts/${id}/trade-count`,
  },
  trades: {
    base: "/api/trades",
    byId: (id: string) => `/api/trades/${id}`,
    summary: (id: string) => `/api/trades/${id}/summary`,
    importPreview: "/api/trades/import/preview",
    importCommit: "/api/trades/import/commit",
  },
  portfolio: {
    summary: "/api/portfolio/summary",
    holding: "/api/portfolio/holding",
  },
  stocks: {
    search: "/api/stocks/search",
    quote: "/api/stocks/quote",
  },
  analysis: {
    dashboard: "/api/analysis/dashboard",
  },
} as const;

// 지연 초기화 싱글턴 — SSR import 시 createBrowserClient 실행을 피하기 위해
// 첫 실제 호출(클라이언트 측) 시점까지 초기화를 미룬다.
let _supabase: ReturnType<typeof createClient> | undefined;
function getSupabase() {
  if (!_supabase) _supabase = createClient();
  return _supabase;
}

async function getBearerHeader(): Promise<Record<string, string>> {
  if (!API_BASE) return {};
  try {
    const { data: { session } } = await getSupabase().auth.getSession();
    if (!session?.access_token) return {};
    return { Authorization: `Bearer ${session.access_token}` };
  } catch {
    return {};
  }
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
    if (!res.ok) throw new ApiError(`API 오류 (${res.status})`, res.status);
    return undefined as T;
  }
  const data = await res.json();
  if (!res.ok) {
    throw new ApiError(
      (data as { error?: string }).error ?? `API 오류 (${res.status})`,
      res.status,
    );
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
  list: () => apiFetch<Account[]>(ROUTES.accounts.base),

  create: (input: AccountInput) =>
    apiFetch<Account>(ROUTES.accounts.base, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  update: (id: string, input: AccountInput) =>
    apiFetch<Account>(ROUTES.accounts.byId(id), {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  delete: (id: string) =>
    apiFetch<void>(ROUTES.accounts.byId(id), { method: "DELETE" }),

  tradeCount: (id: string) =>
    apiFetch<{ count: number }>(ROUTES.accounts.tradeCount(id)),
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
}

export type TradePatchInput = Partial<TradeCreateInput & TradeMetaInput>;

export interface TradesListResponse {
  trades: TradeWithAccount[];
  accounts: Account[];
}

export interface TradeSummary {
  pnl: number;
  result: TradeResult | null;
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
    return apiFetch<TradesListResponse>(`${ROUTES.trades.base}${query}`);
  },

  get: (id: string) => apiFetch<TradeWithAccount>(ROUTES.trades.byId(id)),

  create: (input: TradeCreateInput) =>
    apiFetch<{ id: string; trade_type: TradeType }>(ROUTES.trades.base, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  update: (id: string, patch: TradePatchInput) =>
    apiFetch<void>(ROUTES.trades.byId(id), {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  delete: (id: string) =>
    apiFetch<void>(ROUTES.trades.byId(id), { method: "DELETE" }),

  summary: (id: string) => apiFetch<TradeSummary>(ROUTES.trades.summary(id)),
};

// ============================================================
// Import (거래내역서 파일 업로드)
// ============================================================

export interface ImportErrorItem {
  row_no: number;
  reason: string;
}

export interface ImportPreviewResponse {
  staging_id: string;
  broker_key: string;
  broker_name: string;
  account_hint: string | null;
  new_count: number;
  duplicate_count: number;
  error_count: number;
  usd_skip_count: number;
  unresolved_ticker_count: number;
  errors: ImportErrorItem[];
}

export interface ImportCommitResponse {
  inserted_count: number;
  merged_count: number;
  skipped_count: number;
  error_count: number;
  errors: ImportErrorItem[];
}

export const importApi = {
  preview: async (file: File, brokerKey?: string): Promise<ImportPreviewResponse> => {
    const bearer = await getBearerHeader();
    const formData = new FormData();
    formData.append("file", file);
    const url = `${API_BASE}${ROUTES.trades.importPreview}${brokerKey ? `?broker_key=${brokerKey}` : ""}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { ...bearer },
      body: formData,
    });
    if (!res.ok) {
      let msg = "파일 분석 중 오류가 발생했습니다.";
      try { msg = (await res.json()).detail ?? msg; } catch { /* noop */ }
      throw new ApiError(msg, res.status);
    }
    return res.json();
  },

  commit: (stagingId: string, accountId: string): Promise<ImportCommitResponse> =>
    apiFetch<ImportCommitResponse>(ROUTES.trades.importCommit, {
      method: "POST",
      body: JSON.stringify({ staging_id: stagingId, account_id: accountId }),
    }),
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
  summary: () => apiFetch<PortfolioSummaryResponse>(ROUTES.portfolio.summary),

  holding: (params: PortfolioHoldingParams) => {
    const entries: Record<string, string> = {
      accountId: params.accountId,
      assetName: params.assetName,
      country: params.country,
    };
    if (params.ticker) entries.ticker = params.ticker;
    return apiFetch<PortfolioHoldingResponse>(
      `${ROUTES.portfolio.holding}?${new URLSearchParams(entries)}`
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
    apiFetch<StockSearchResult[]>(`${ROUTES.stocks.search}?q=${encodeURIComponent(q)}`),

  quote: (symbols: string) =>
    apiFetch<Record<string, { price: number; currency: string; as_of: string }>>(
      `${ROUTES.stocks.quote}?symbols=${encodeURIComponent(symbols)}`
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

export interface AnalysisDashboardData {
  period: Period;
  summary: AnalysisSummary;
  behavior: BehaviorData;
  suggestions: SuggestionsData;
  missingQuoteTickers: string[];
}

export const analysisApi = {
  dashboard: (period: Period) =>
    apiFetch<AnalysisDashboardData>(
      `${ROUTES.analysis.dashboard}?period=${period}`,
    ),
};
