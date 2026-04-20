import type { StrategyType } from "@/types/database";

// 임계값 상수 — 추후 튜닝 가능
export const STRATEGY_THRESHOLDS = {
  SCALPING_MAX_DAYS: 1,
  SWING_MAX_DAYS: 30,
} as const;

export type StrategyAdherence = "FOLLOWED" | "DEVIATED" | "UNKNOWN";

export interface StrategyEvaluation {
  planned: StrategyType | null;
  actual: StrategyType;
  holdingDays: number;
  adherence: StrategyAdherence;
}

// FIFO 가중평균 보유일수 → 실제 전략 역산
export function inferActualStrategy(holdingDays: number): StrategyType {
  if (holdingDays <= STRATEGY_THRESHOLDS.SCALPING_MAX_DAYS) return "SCALPING";
  if (holdingDays <= STRATEGY_THRESHOLDS.SWING_MAX_DAYS) return "SWING";
  return "LONG_TERM";
}

// 계획 전략 vs 실제 보유일수 기반 전략 비교
export function evaluateStrategyAdherence(
  plannedStrategy: StrategyType | null,
  holdingDays: number,
): StrategyEvaluation {
  const actual = inferActualStrategy(holdingDays);

  if (!plannedStrategy || plannedStrategy === "UNKNOWN") {
    return { planned: plannedStrategy ?? null, actual, holdingDays, adherence: "UNKNOWN" };
  }

  const adherence: StrategyAdherence = actual === plannedStrategy ? "FOLLOWED" : "DEVIATED";
  return { planned: plannedStrategy, actual, holdingDays, adherence };
}
