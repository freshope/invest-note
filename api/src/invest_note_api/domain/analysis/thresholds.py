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
WIN_THRESHOLD = 60
LOSS_THRESHOLD = 40
