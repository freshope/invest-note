"""분석 임계값 단일 SOT (백엔드).

frontend `app/src/lib/constants/analysis.ts` 와 값이 일치해야 한다.
임계값 변경 시 두 파일을 함께 수정한다 (`docs/decisions.md` 참고).
"""
from __future__ import annotations

# 전략별 보유일 임계값
SCALPING_MAX_DAYS = 1
SWING_MAX_DAYS = 30

# HHI 집중도 임계값
HHI_HIGH = 0.5
HHI_MID = 0.25
TOP1_WEIGHT_HIGH = 0.4

# 승률 임계값 (%)
WIN_THRESHOLD = 65
LOSS_THRESHOLD = 40

# 도메인 판정 임계값 — rules.py 규칙 평가에서 사용
FEELING_RATE_HIGH = 40            # _rule_feeling_heavy: '감/직감' 비율(%) 상한
REFLECTION_RATE_LOW = 30          # _rule_no_reflection: 회고 작성률(%) 하한
LOSING_STRATEGY_RATE = 30         # _rule_losing_strategy: 손실 전략 승률(%) 임계
MISSING_TAG_RATE_HIGH = 30        # _rule_tag_missing: 태그 누락률(%) 상한
RESULT_INPUT_RATE_LOW = 50        # _rule_result_missing/_rule_high_winrate: 결과 입력률(%) 하한
SCALPING_HOLDING_LIMIT_DAYS = 7   # _rule_holding_mismatch: 스캘핑 평균 보유일 한계

# 최소 샘플 가드 — 통계적 신뢰도를 확보하기 위한 최소 거래/결과 수
MIN_EMOTION_TRADES = 5            # _rule_fomo/_rule_calm: 감정별 최소 거래 수
MIN_EMOTION_RESULTS = 3           # _rule_fomo: 감정별 최소 결과 수
MIN_TOTAL_TRADES = 5              # _rule_feeling_heavy/_rule_tag_missing: 전체 최소 거래 수
MIN_SELL_TRADES = 3               # _rule_no_reflection/_rule_result_missing: 최소 매도 수
MIN_HIGH_WINRATE_SELL = 5         # _rule_high_winrate: 고승률 판정 최소 매도 수
MIN_SCALPING_TRADES = 3           # _rule_holding_mismatch: 스캘핑 분류 최소 거래 수
MIN_STRATEGY_TRADES = 5           # _rule_losing_strategy: 전략별 최소 거래 수
MIN_STRATEGY_RESULTS = 3          # _rule_losing_strategy: 전략별 최소 결과 수
