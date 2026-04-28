import type { MarketType, TradeResult } from "@/types/database";

export const MARKET_LABELS: Record<MarketType, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

// 거래 자동 계산용 수수료/세율 (정확한 부과 금액은 백엔드/증권사 책임)
export const COMMISSION_RATE = 0.00015;
export const SELL_TAX_RATE = 0.0018;

export const STRATEGY_LABELS: Record<string, string> = {
  SCALPING: "스캘핑",
  SWING: "스윙",
  LONG_TERM: "장기",
  UNKNOWN: "미분류",
};

export const ADHERENCE_CONFIG = {
  FOLLOWED: {
    label: "전략 준수 ✓",
    textClassName: "text-green-600",
    bgClassName: "bg-green-50 border-green-200",
    barClassName: "bg-green-500",
  },
  DEVIATED: {
    label: "전략 이탈 ✗",
    textClassName: "text-orange-600",
    bgClassName: "bg-orange-50 border-orange-200",
    barClassName: "bg-orange-500",
  },
  UNKNOWN: {
    label: "분류 불가",
    textClassName: "text-muted-foreground",
    bgClassName: "bg-muted border-border",
    barClassName: "bg-muted-foreground/40",
  },
} as const;

export const EMOTION_LABELS: Record<string, string> = {
  CONFIDENT: "확신",
  ANXIOUS: "불안",
  FOMO: "FOMO",
  IMPULSIVE: "충동",
  CALM: "평온",
};

export const RESULT_LABELS: Record<string, string> = {
  SUCCESS: "수익",
  FAIL: "손실",
  BREAKEVEN: "본전",
};

export const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];
