"""FIFO 가중평균 보유일 계산 — 모든 SELL에 대해 dict로 반환."""
from __future__ import annotations

from typing import TYPE_CHECKING

from invest_note_api.domain.trade_utils import to_kst

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade

_MS_PER_DAY = 1000 * 60 * 60 * 24


def compute_holding_days_map(trades: list[Trade]) -> dict[str, int]:
    """각 SELL trade.id → FIFO 기준 가중평균 보유 기간(일)."""
    result: dict[str, int] = {}
    sorted_trades = sorted(trades, key=lambda t: t.traded_at)

    queue_map: dict[str, list[dict]] = {}

    for trade in sorted_trades:
        key = f"{trade.ticker_symbol or trade.asset_name}:{trade.country_code or 'KR'}"
        if key not in queue_map:
            queue_map[key] = []
        queue = queue_map[key]

        if trade.trade_type == "BUY":
            queue.append({"qty": trade.quantity, "time_ms": int(to_kst(trade.traded_at).timestamp() * 1000)})
        else:
            remaining = trade.quantity
            sell_time_ms = int(to_kst(trade.traded_at).timestamp() * 1000)
            weighted_ms = 0.0
            total_consumed = 0.0

            while remaining > 0 and queue:
                slot = queue[0]
                consume = min(slot["qty"], remaining)
                weighted_ms += (sell_time_ms - slot["time_ms"]) * consume
                total_consumed += consume
                remaining -= consume
                slot["qty"] -= consume
                if slot["qty"] <= 0:
                    queue.pop(0)

            if total_consumed > 0:
                result[trade.id] = round(weighted_ms / total_consumed / _MS_PER_DAY)
            else:
                result[trade.id] = 0

    return result
