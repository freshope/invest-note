"""저장된 보유일을 모든 SELL에 대해 dict로 반환."""
from __future__ import annotations

from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import TRADE_TYPE_SELL

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


def compute_holding_days_map(trades: list[Trade]) -> dict[str, int]:
    """각 SELL trade.id → 저장된 보유 기간(일)."""
    result: dict[str, int] = {}
    for trade in trades:
        if trade.trade_type == TRADE_TYPE_SELL and trade.holding_days is not None:
            result[trade.id] = trade.holding_days

    return result
