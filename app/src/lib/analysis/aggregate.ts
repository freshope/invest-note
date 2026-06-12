// BE `/analysis/dashboard` 응답의 `summary` 필드 타입 정의.
// 분석 집계 자체는 BE(`api/.../domain/analysis/aggregate.py`)가 단독 SOT로 담당하며,
// FE는 BE 응답을 그대로 표시한다.

import type { Period } from "./period";
import type { StrategyAdherence } from "./strategy-adherence";

export interface StrategyStats {
  type: string;
  count: number;
  resultCount: number;
  winRate: number;
  sumPnL: number;
  avgHoldingDays: number;
}

export interface EmotionStats {
  type: string;
  count: number;
  resultCount: number;
  winRate: number;
  sumPnL: number;
}

export interface TagStats {
  tag: string;
  count: number;
  winRate: number;
  sumPnL: number;
}

export interface StrategyAdherenceStats {
  type: StrategyAdherence;
  count: number;
  resultCount: number;
  winRate: number;
  sumPnL: number;
}

export interface AnalysisSummary {
  period?: Period;
  totalTrades: number;
  sellTrades: number;
  winRate: number;
  totalProfitLoss: number;
  byStrategy: StrategyStats[];
  byEmotion: EmotionStats[];
  byTag: TagStats[];
  missingTagRate: number;
  feelingRate: number;
  reflectionRate: number;
  strategyAdherenceRate: number;
  byStrategyAdherence: StrategyAdherenceStats[];
}
