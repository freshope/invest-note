import type { Period } from "@/lib/analysis/period";

export const queryKeys = {
  portfolio: ["portfolio"] as const,
  portfolioSummary: (accountId: string | null) =>
    ["portfolio", "summary", accountId] as const,

  // portfolio 트리 하위로 묶어서 portfolio invalidate 한 번으로 함께 무효화되도록 함
  accounts: ["portfolio", "accounts"] as const,

  trades: ["trades"] as const,
  trade: (id: string) => ["trade", id] as const,
  tradeSummary: (id: string) => ["trade-summary", id] as const,

  holding: (
    accountId: string,
    tickerSymbol: string,
    assetName: string,
    countryCode: string,
  ) => ["holding", accountId, tickerSymbol, assetName, countryCode] as const,

  stockSearch: (q: string) => ["stocks", "search", q] as const,

  // 시세는 portfolio 트리와 별개 — 독립 staleTime(45s). keys 는 정렬해 안정적 캐시 키 보장.
  quotes: (keys: string[]) => ["quotes", [...keys].sort().join(",")] as const,

  // 종목 메타(마켓/시총순위/연금) — 일단위 갱신이라 긴 staleTime. codes 정렬로 안정적 캐시 키.
  stockMeta: (codes: string[]) => ["stock-meta", [...codes].sort().join(",")] as const,

  analysisDashboard: (period: Period) =>
    ["analysis", "dashboard", period] as const,

  assetHistory: (accountId: string | null, ticker: string | null) =>
    ["assets", "history", accountId, ticker] as const,
};
