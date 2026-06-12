"""분석 도메인 공용 수학 헬퍼."""
from __future__ import annotations


def _percent(numer: float, denom: int) -> float:
    return numer / denom * 100 if denom else 0.0
