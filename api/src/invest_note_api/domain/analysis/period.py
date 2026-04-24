"""기간 필터 — period 파싱 + KST 경계 계산."""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from invest_note_api.domain.trade_utils import KST, to_kst

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade

Period = Literal["1m", "3m", "6m", "ytd", "all"]
DEFAULT_PERIOD: Period = "all"

_KST = KST


def parse_period(param: str | None) -> Period:
    if param in ("1m", "3m", "6m", "ytd", "all"):
        return param  # type: ignore[return-value]
    return "all"


def _sub_months(dt: datetime, n: int) -> datetime:
    month = dt.month - n
    year = dt.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _period_to_range(period: Period) -> tuple[datetime | None, datetime]:
    now = datetime.now(_KST)
    if period == "all":
        return None, now
    if period == "ytd":
        from_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return from_dt, now
    months = {"1m": 1, "3m": 3, "6m": 6}[period]
    base = _sub_months(now, months)
    from_dt = base.replace(hour=0, minute=0, second=0, microsecond=0)
    return from_dt, now


def filter_by_period(trades: list[Trade], period: Period) -> list[Trade]:
    from_dt, to_dt = _period_to_range(period)
    to_ts = to_dt.timestamp()
    from_ts = from_dt.timestamp() if from_dt else None

    result = []
    for t in trades:
        ts = to_kst(t.traded_at).timestamp()
        if from_ts is not None and ts < from_ts:
            continue
        if ts <= to_ts:
            result.append(t)
    return result
