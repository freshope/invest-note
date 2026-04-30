import type {
  EmotionType,
  MarketType,
  ReasoningTag,
  StrategyType,
  TradeResult,
} from "@/types/database";
import { PNL_COLORS } from "./colors";

export const MARKET_LABELS: Record<MarketType, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

// 거래 자동 계산용 수수료/세율 (정확한 부과 금액은 백엔드/증권사 책임)
export const COMMISSION_RATE = 0.00015;
export const SELL_TAX_RATE = 0.0018;

export const STRATEGIES: { value: StrategyType; label: string }[] = [
  { value: "SCALPING", label: "스캘핑" },
  { value: "SWING", label: "스윙" },
  { value: "LONG_TERM", label: "장기" },
  { value: "UNKNOWN", label: "없음" },
];

export const EMOTIONS: { value: EmotionType; label: string }[] = [
  { value: "CONFIDENT", label: "확신 😊" },
  { value: "ANXIOUS", label: "불안 😰" },
  { value: "FOMO", label: "FOMO 😤" },
  { value: "IMPULSIVE", label: "충동 ⚡" },
  { value: "CALM", label: "평온 😌" },
];

export const REASONING_TAGS: { value: ReasoningTag; label: string }[] = [
  { value: "TECHNICAL", label: "기술적 분석" },
  { value: "FUNDAMENTAL", label: "펀더멘탈" },
  { value: "NEWS", label: "뉴스/이슈" },
  { value: "FEELING", label: "감/직감" },
];

export const STRATEGY_LABELS: Record<string, string> = Object.fromEntries(
  STRATEGIES.map((s) => [s.value, s.label]),
);

// 분석 집계의 미입력 버킷 라벨. BE의 EMOTION_UNTAGGED/TAG_UNTAGGED와 동일한 키.
// 폼 옵션 배열(EMOTIONS, REASONING_TAGS)에는 추가하지 않는다 — 사용자 선택 불가.
const UNTAGGED_KEY = "UNTAGGED";

export const EMOTION_LABELS: Record<string, string> = {
  ...Object.fromEntries(EMOTIONS.map((e) => [e.value, e.label])),
  [UNTAGGED_KEY]: "미입력",
};

export const REASONING_TAG_LABELS: Record<string, string> = {
  ...Object.fromEntries(REASONING_TAGS.map((t) => [t.value, t.label])),
  [UNTAGGED_KEY]: "미입력",
};

// satisfies로 database.ts의 타입과 동기화 보장
export const STRATEGY_VALUES = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"] as const satisfies readonly StrategyType[];
export const EMOTION_VALUES = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"] as const satisfies readonly EmotionType[];
export const REASONING_TAG_VALUES = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"] as const satisfies readonly ReasoningTag[];
export const TRADE_RESULT_VALUES = ["SUCCESS", "FAIL", "BREAKEVEN"] as const satisfies readonly TradeResult[];

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

export const RESULT_LABELS: Record<string, string> = {
  SUCCESS: "수익",
  FAIL: "손실",
  BREAKEVEN: "본전",
};

export const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: `${PNL_COLORS.rise.bg} text-white ${PNL_COLORS.rise.border}` },
  { value: "FAIL", label: "손실 ❌", color: `${PNL_COLORS.fall.bg} text-white ${PNL_COLORS.fall.border}` },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];
