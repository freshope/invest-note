"""PnL 동기화 — recalc_group_pnl.

의도적 동작 변경: Next.js는 Promise.all 병렬 개별 UPDATE + 실패 허용.
FastAPI는 acquire_for_user 트랜잭션 내 executemany → all-or-nothing.
실패 시 APIError(500) + 자동 ROLLBACK. 정합성↑ / 복원력↓.
"""
from __future__ import annotations

import math
import operator
from collections.abc import Callable
from typing import Any

from invest_note_api.domain.realized_pnl import (
    GroupPnLEntry,
    TradeGroupKey,
    compute_group_pnl,
)
from invest_note_api.domain.trade_types import Trade
from invest_note_api.errors import APIError


def _float_eq(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


# (attr, equality 비교 함수) — _is_changed 가 순회한다.
# 부동소수 두 필드는 DB round-trip 미세 오차 방지를 위해 _float_eq, 나머지는 ==.
_COMPARE_FIELDS: list[tuple[str, Callable[[Any, Any], bool]]] = [
    ("profit_loss", _float_eq),
    ("avg_buy_price", _float_eq),
    ("holding_days", operator.eq),
    ("strategy_type", operator.eq),
    ("reasoning_tags", operator.eq),
    ("custom_tags", operator.eq),
    ("emotion", operator.eq),
    ("result", operator.eq),
]


def _is_changed(existing: Trade | None, entry: GroupPnLEntry) -> bool:
    if existing is None:
        return True
    return any(
        not eq(getattr(existing, attr), getattr(entry, attr))
        for attr, eq in _COMPARE_FIELDS
    )


async def recalc_group_pnl(
    conn: Any,
    trades: list[Trade],
    key: TradeGroupKey,
) -> None:
    """그룹 PnL 재계산 후 변경된 SELL 거래에만 UPDATE 발행."""
    pnl_map = compute_group_pnl(trades, key)
    if not pnl_map:
        return

    existing_by_id: dict[str, Trade] = {t.id: t for t in trades}

    rows = [
        (
            entry.profit_loss,
            entry.avg_buy_price,
            entry.holding_days,
            entry.strategy_type,
            entry.reasoning_tags,
            entry.custom_tags,
            entry.emotion,
            entry.result,
            sell_id,
        )
        for sell_id, entry in pnl_map.items()
        if _is_changed(existing_by_id.get(sell_id), entry)
    ]

    if not rows:
        return

    try:
        await conn.executemany(
            "UPDATE trades SET profit_loss = $1, avg_buy_price = $2, holding_days = $3, "
            "strategy_type = $4, reasoning_tags = $5, custom_tags = $6, emotion = $7, "
            "result = $8 WHERE id = $9",
            rows,
        )
    except Exception as exc:
        raise APIError(f"PnL 동기화 실패: {exc}", 500) from exc
