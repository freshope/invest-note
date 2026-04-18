import type { TradeType, MarketType, StrategyType, EmotionType, ReasoningTag, TradeResult } from "@/types/database";

// ============================================================
// Account validators
// ============================================================

export const MAX_NAME_LENGTH = 50;
export const MAX_BROKER_LENGTH = 50;
const MAX_CASH_BALANCE = 9999999999999999.99;

export function parseCashBalance(raw: unknown): number | null {
  if (raw == null || raw === "") return 0;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num < 0 || num > MAX_CASH_BALANCE) return null;
  return num;
}

// ============================================================
// Trade validators
// ============================================================

export const VALID_TRADE_TYPES: TradeType[] = ["BUY", "SELL"];
export const VALID_MARKET_TYPES: MarketType[] = ["STOCK", "CRYPTO", "ETC"];
export const VALID_COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
export type CountryCode = (typeof VALID_COUNTRY_CODES)[number];
export const VALID_STRATEGIES: StrategyType[] = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"];
export const VALID_EMOTIONS: EmotionType[] = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"];
export const VALID_REASONING_TAGS: ReasoningTag[] = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"];
export const VALID_RESULTS: TradeResult[] = ["SUCCESS", "FAIL", "BREAKEVEN"];

export function parsePositiveNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return null;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num <= 0) return null;
  return num;
}

export function parseNonNegativeNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return 0;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num < 0) return null;
  return num;
}

export function parseNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return null;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num)) return null;
  return num;
}

// "yyyy-MM-dd'T'HH:mm" 형식 입력을 KST(+09:00)로 해석해 ISO 문자열 반환
export function parseTradedAt(raw: string): string {
  return new Date(`${raw}+09:00`).toISOString();
}
