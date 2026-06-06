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
import type { DashboardTotals, Position, AccountSnapshot, QuoteMap } from "@/lib/portfolio";
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
    base: "/accounts",
    byId: (id: string) => `/accounts/${id}`,
    tradeCount: (id: string) => `/accounts/${id}/trade-count`,
  },
  trades: {
    base: "/trades",
    byId: (id: string) => `/trades/${id}`,
    summary: (id: string) => `/trades/${id}/summary`,
    bulkDelete: "/trades/bulk-delete",
    importPreview: "/trades/import/preview",
    importCommit: "/trades/import/commit",
  },
  portfolio: {
    summary: "/portfolio/summary",
    holding: "/portfolio/holding",
  },
  stocks: {
    search: "/stocks/search",
    quote: "/stocks/quote",
    meta: "/stocks/meta",
  },
  analysis: {
    dashboard: "/analysis/dashboard",
  },
  assets: {
    history: "/assets/history",
  },
  me: {
    base: "/me",
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
  buyReason?: string | null;
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

  /**
   * 거래 일괄 삭제. 1~200건. 단일 트랜잭션 — 전부 성공(204) 또는 전부 롤백(400/404).
   */
  bulkDelete: (ids: string[]) =>
    apiFetch<void>(ROUTES.trades.bulkDelete, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

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
  /** 선택 계좌 기준 정합성 위반 (oversell 등). 해당 종목 그룹은 commit 시 BE 가 skip; FE 는 사용자에게 노출만 한다. */
  validation_errors: ImportErrorItem[];
  /** validation_errors 로 제외 예정인 그룹들의 import row 합계. 카운트 카드 보정용. */
  excluded_count: number;
}

export interface ImportCommitResponse {
  inserted_count: number;
  merged_count: number;
  skipped_count: number;
  error_count: number;
  errors: ImportErrorItem[];
}

export const importApi = {
  preview: async (
    file: File,
    brokerKey?: string,
    accountId?: string,
  ): Promise<ImportPreviewResponse> => {
    const bearer = await getBearerHeader();
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams();
    if (brokerKey) params.set("broker_key", brokerKey);
    if (accountId) params.set("account_id", accountId);
    const qs = params.toString();
    const url = `${API_BASE}${ROUTES.trades.importPreview}${qs ? `?${qs}` : ""}`;
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
  // withQuotes=false (옵션 B) 면 BE 가 시세 fetch 를 건너뛰고 즉시 응답한다.
  // 신규 FE 는 항상 false 를 보내고 시세는 stocksApi.quote 로 병렬 조회해 overlay 한다.
  // refresh=true (pull-to-refresh) 는 withQuotes=false 에서 no-op(시세 fetch 자체 skip)이나
  // 시그니처는 유지한다.
  summary: (accountId?: string | null, refresh = false, withQuotes = true) => {
    const params: Record<string, string> = {};
    if (accountId) params.accountId = accountId;
    if (refresh) params.refresh = "1";
    if (!withQuotes) params.withQuotes = "false";
    const qs = Object.keys(params).length ? `?${new URLSearchParams(params)}` : "";
    return apiFetch<PortfolioSummaryResponse>(`${ROUTES.portfolio.summary}${qs}`);
  },

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

// 종목 메타(뱃지용). 키는 BE 와 동일하게 snake_case 로 통과시킨다(/stocks/quote 와 일관).
export interface StockMeta {
  market: string;
  marcap_rank: number | null;
  nps_holding: "held" | "major" | null;
  nps_as_of: string | null;
}
export type StockMetaMap = Record<string, StockMeta>;

export const stocksApi = {
  search: (q: string) =>
    apiFetch<StockSearchResult[]>(`${ROUTES.stocks.search}?q=${encodeURIComponent(q)}`),

  // refresh=true (pull-to-refresh) 면 BE 시세 캐시(45s)를 우회해 새 시세를 받는다.
  quote: (symbols: string, refresh = false) =>
    apiFetch<QuoteMap>(
      `${ROUTES.stocks.quote}?symbols=${encodeURIComponent(symbols)}${refresh ? "&refresh=1" : ""}`
    ),

  meta: (codes: string) =>
    apiFetch<StockMetaMap>(`${ROUTES.stocks.meta}?codes=${encodeURIComponent(codes)}`),
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
  // refresh=true (pull-to-refresh) 면 BE 시세 캐시를 우회해 새 시세를 받는다.
  dashboard: (period: Period, refresh = false) =>
    apiFetch<AnalysisDashboardData>(
      `${ROUTES.analysis.dashboard}?period=${period}${refresh ? "&refresh=1" : ""}`,
    ),
};

// ============================================================
// Assets (일별 자산 변화)
// ============================================================

/** 차트 점: 일별 자산(보유 종목 평가액 합) */
export interface AssetHistoryPoint {
  date: string;
  value: number;
}

/**
 * 목록 행. `change` 는 전일대비 value 차(첫 항목 0).
 * 종목뷰(ticker 지정)일 때만 `close`(그 날 종가)·`qty`(보유수량)를 포함한다.
 */
export interface AssetHistoryItem {
  date: string;
  value: number;
  change: number;
  close?: number | null;
  qty?: number;
}

export interface AssetHistoryResponse {
  series: AssetHistoryPoint[];
  items: AssetHistoryItem[];
  /** 일부 종목 fetch 실패로 carry-forward/결측 존재 시 true (부분표시 배지) */
  incomplete: boolean;
  /** 마지막 점 기준시각(오늘 점은 라이브 시세). ISO 문자열. */
  asOf: string;
  /** 현재 보유분 매수 원금(cost_basis 합). 손익 가이드 라인 기준. 보유 없음이면 null. */
  investedAmount: number | null;
}

export interface AssetHistoryParams {
  accountId?: string | null;
  ticker?: string | null;
  country?: string | null;
}

export const assetsApi = {
  history: (params: AssetHistoryParams) => {
    const entries: Record<string, string> = {};
    if (params.accountId) entries.accountId = params.accountId;
    if (params.ticker) entries.ticker = params.ticker;
    if (params.country) entries.country = params.country;
    const qs = Object.keys(entries).length ? `?${new URLSearchParams(entries)}` : "";
    return apiFetch<AssetHistoryResponse>(`${ROUTES.assets.history}${qs}`);
  },
};

// ============================================================
// Me / Account
// ============================================================

export const meApi = {
  deleteAccount: () => apiFetch<void>(ROUTES.me.base, { method: "DELETE" }),
};
