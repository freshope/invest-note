import type {
  EmotionType,
  MarketType,
  ReasoningTag,
  StrategyType,
  TradeResult,
  TradeType,
} from "@/types/database";
import { PNL_COLORS } from "./pnl-colors";
import { SEMANTIC_COLORS } from "./semantic-colors";

export const MARKET_LABELS: Record<MarketType, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

export const TRADE_TYPE_LABELS: Record<TradeType, string> = {
  BUY: "매수",
  SELL: "매도",
};

export const TRADE_TYPE = {
  BUY: "BUY",
  SELL: "SELL",
} as const satisfies Record<string, TradeType>;

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
export const UNTAGGED_KEY = "UNTAGGED";

// 전략 미입력(STRATEGIES의 "없음") 버킷 키. 분석 섹션에서 마지막 위치 + muted 처리에 사용.
export const STRATEGY_UNKNOWN_KEY = "UNKNOWN";

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
    textClassName: SEMANTIC_COLORS.success.text,
    bgClassName: `${SEMANTIC_COLORS.success.bgSoft} ${SEMANTIC_COLORS.success.borderSoft}`,
    barClassName: SEMANTIC_COLORS.success.bg,
  },
  DEVIATED: {
    // 이탈은 경고색(amber/warning) — 옛 orange 를 semantic warning 토큰으로 통일.
    label: "전략 이탈 ✗",
    textClassName: SEMANTIC_COLORS.warning.text,
    bgClassName: `${SEMANTIC_COLORS.warning.bgSoft} ${SEMANTIC_COLORS.warning.borderSoft}`,
    barClassName: SEMANTIC_COLORS.warning.bg,
  },
  UNKNOWN: {
    label: "미입력",
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
