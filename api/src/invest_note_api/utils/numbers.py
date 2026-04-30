"""숫자 파싱 공용 유틸."""

from __future__ import annotations

import math


def strip_comma_number(value: object) -> object:
    """숫자 파싱 직전 정규화 헬퍼.

    문자열 입력은 쉼표를 제거하고 양옆 공백을 strip한 문자열로 반환한다.
    그 외(int, float, Decimal, None 등)는 변경 없이 반환한다.
    """
    if isinstance(value, str):
        return value.replace(",", "").strip()
    return value


def half_up_int(x: float) -> int:
    """JS Math.round 동작과 동일한 HALF_UP 정수 반올림."""
    return math.floor(x + 0.5)
