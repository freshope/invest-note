"""PnL 동기화 — recalc_group_pnl.

의도적 동작 변경: Next.js는 Promise.all 병렬 개별 UPDATE + 실패 허용.
FastAPI는 acquire_for_user 트랜잭션 내 executemany → all-or-nothing.
실패 시 APIError(500) + 자동 ROLLBACK. 정합성↑ / 복원력↓.
"""
from __future__ import annotations

from typing import Any

from invest_note_api.domain.realized_pnl import TradeGroupKey, compute_group_pnl
from invest_note_api.domain.trade_types import Trade
from invest_note_api.errors import APIError


async def recalc_group_pnl(
    conn: Any,
    trades: list[Trade],
    key: TradeGroupKey,
) -> None:
    """그룹 PnL 재계산 후 SELL 거래에 일괄 UPDATE."""
    pnl_map = compute_group_pnl(trades, key)
    if not pnl_map:
        return

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
    ]

    try:
        await conn.executemany(
            "UPDATE trades SET profit_loss = $1, avg_buy_price = $2, holding_days = $3, "
            "strategy_type = $4, reasoning_tags = $5, emotion = $6, result = $7 WHERE id = $8",
            rows,
        )
    except Exception as exc:
        raise APIError(f"PnL 동기화 실패: {exc}", 500) from exc
