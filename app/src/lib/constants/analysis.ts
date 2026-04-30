export type Period = "1m" | "3m" | "6m" | "ytd" | "all";

// 대시보드 진입 시 기본 기간
export const DEFAULT_ANALYSIS_PERIOD: Period = "3m";

export const PERIODS_FULL: { value: Period; label: string }[] = [
  { value: "1m", label: "1개월" },
  { value: "3m", label: "3개월" },
  { value: "6m", label: "6개월" },
  { value: "ytd", label: "올해(YTD)" },
  { value: "all", label: "전체" },
];

export const PERIODS_COMPACT: { value: Period; label: string }[] = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "ytd", label: "올해" },
  { value: "all", label: "전체" },
];

// HHI 집중도 임계치 (FE UI 라벨 결정용 — DiversificationPanel)
export const HHI_HIGH = 0.5;
export const HHI_MID = 0.25;

// 승률 임계치 (%) — FE UI 색상 결정용 (WinRateBar, SummaryCards)
export const WIN_THRESHOLD = 65;
export const LOSS_THRESHOLD = 40;

// 결과 입력률 임계치 (%) — 승률 표시 신뢰도 컷오프 (SummaryCards)
export const RESULT_INPUT_RATE_LOW = 50;
