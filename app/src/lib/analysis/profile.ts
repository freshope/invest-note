export interface BehaviorProfile {
  tempo: number;             // 0(스캘퍼) ~ 100(장기)
  diversification: number;   // 0(집중형) ~ 100(분산형) — 현재 보유 포트폴리오 기준
  emotionStability: number;  // 0(충동형) ~ 100(차분형)
  reasoningQuality: number;  // 0(감각형) ~ 100(분석형)
  reviewHabit: number;       // 0(무복기) ~ 100(복기형)
}

export interface ProfileInputRates {
  holdingDays: number;   // SELL 중 계산 가능한 비율
  emotion: number;       // 전체 거래 중 emotion 입력 비율
  reasoningTag: number;  // BUY 중 태그 입력 비율
  result: number;        // SELL 중 result 입력 비율
  reflection: number;    // SELL 중 sell_reason 작성 비율
}
