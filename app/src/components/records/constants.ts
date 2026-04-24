import type { StrategyType, EmotionType, ReasoningTag, TradeResult } from "@/types/database";

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

export const EMOTION_LABELS: Record<string, string> = Object.fromEntries(
  EMOTIONS.map((e) => [e.value, e.label]),
);

export const REASONING_TAG_LABELS: Record<string, string> = Object.fromEntries(
  REASONING_TAGS.map((t) => [t.value, t.label]),
);

// satisfies로 database.ts의 타입과 동기화 보장
export const STRATEGY_VALUES = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"] as const satisfies readonly StrategyType[];
export const EMOTION_VALUES = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"] as const satisfies readonly EmotionType[];
export const REASONING_TAG_VALUES = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"] as const satisfies readonly ReasoningTag[];
export const TRADE_RESULT_VALUES = ["SUCCESS", "FAIL", "BREAKEVEN"] as const satisfies readonly TradeResult[];
