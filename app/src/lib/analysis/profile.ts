export interface BehaviorProfile {
  tempo: number;              // 0(스캘퍼) ~ 100(장기), 중앙값 보유일 기반
  emotionStability: number;   // 0(불안정) ~ 100(안정), 데이터 없으면 0
  reasoningQuality: number;   // 0(감각형) ~ 100(분석형)
  reviewHabit: number;        // 0(무복기) ~ 100(복기형)
  strategyConsistency: number; // 0(이탈형) ~ 100(준수형), planned vs actual
}

export interface ProfileInputRates {
  holdingDays: number;   // SELL 중 보유일 계산 가능 비율
  emotion: number;       // 전체 거래 중 emotion 입력 비율
  reasoningTag: number;  // BUY 중 태그 입력 비율
  result: number;        // SELL 중 result 입력 비율
  reflection: number;    // SELL 중 sell_reason 작성 비율
  strategy: number;      // SELL 중 전략 판정 가능 비율 (planned + holding_days)
}
