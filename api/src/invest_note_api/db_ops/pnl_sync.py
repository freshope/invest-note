"""PnL 동기화 — recalc_group_pnl.

의도적 동작 변경: Next.js는 Promise.all 병렬 개별 UPDATE + 실패 허용.
FastAPI는 acquire_for_user 트랜잭션 내 executemany → all-or-nothing.
실패 시 APIError(500) + 자동 ROLLBACK. 정합성↑ / 복원력↓.
"""
from __future__ import annotations

import math
from typing import Any

from invest_note_api.domain.realized_pnl import (
    GroupPnLEntry,
    TradeGroupKey,
    compute_group_pnl,
)
from invest_note_api.domain.trade_types import Trade
from invest_note_api.errors import APIError


def _is_changed(existing: Trade | None, entry: GroupPnLEntry) -> bool:
    """기존 SELL row의 PnL 7필드와 신규 entry 비교.

    DB round-trip 후의 부동소수 미세 오차로 false-positive UPDATE가 발생하지 않도록
    숫자 필드는 math.isclose로 비교. None ↔ 값 전이는 항상 변경으로 간주.
    """
    if existing is None:
        return True
    if not _float_eq(existing.profit_loss, entry.profit_loss):
        return True
    if not _float_eq(existing.avg_buy_price, entry.avg_buy_price):
        return True
    if existing.holding_days != entry.holding_days:
        return True
    if existing.strategy_type != entry.strategy_type:
        return True
    if existing.reasoning_tags != entry.reasoning_tags:
        return True
    if existing.emotion != entry.emotion:
        return True
    if existing.result != entry.result:
        return True
    return False


def _float_eq(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


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
            "strategy_type = $4, reasoning_tags = $5, emotion = $6, result = $7 WHERE id = $8",
            rows,
        )
    except Exception as exc:
        raise APIError(f"PnL 동기화 실패: {exc}", 500) from exc
