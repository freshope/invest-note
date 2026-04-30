"""Accounts row-level 변환 헬퍼.

API 응답 직전에 asyncpg.Record 의 cash_balance(Decimal) 를 JSON 직렬화
가능한 float 로 강제 변환한다. uuid str 변환 등 호출자별 차이는 호출 측이
책임진다.
"""
from __future__ import annotations

from typing import Any


def account_row_to_dict(row: Any) -> dict:
    d = dict(row)
    if "cash_balance" in d and d["cash_balance"] is not None:
        d["cash_balance"] = float(d["cash_balance"])
    return d
