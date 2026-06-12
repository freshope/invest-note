// 전략 준수 평가 타입 정의. 평가 자체는 BE(`api/.../domain/analysis/strategy_adherence.py`)가
// 담당하며, FE는 BE 응답(`AnalysisSummary.byStrategyAdherence`)을 그대로 표시한다.

import type { StrategyType } from "@/types/database";

export type StrategyAdherence = "FOLLOWED" | "DEVIATED" | "UNKNOWN";

export interface StrategyEvaluation {
  planned: StrategyType | null;
  actual: StrategyType;
  holdingDays: number;
  adherence: StrategyAdherence;
}
