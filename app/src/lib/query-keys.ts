import type { Period } from "@/lib/analysis/period";

export const queryKeys = {
  portfolio: ["portfolio"] as const,
  portfolioSummary: ["portfolio", "summary"] as const,

  accounts: ["accounts"] as const,

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

  analysisSummary: (period: Period) => ["analysis", "summary", period] as const,
  analysisBehavior: (period: Period) => ["analysis", "behavior", period] as const,
  analysisSuggestions: (period: Period) =>
    ["analysis", "suggestions", period] as const,
};
