from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    is_same_group,
)
from invest_note_api.domain.trade_utils import sort_by_traded_at
from invest_note_api.domain.trade_walker import WalkerState, walk_trades

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


@dataclass
class SellBreakdown:
    sell_price: float
    quantity: float
    avg_cost_price: float
    sell_amount: float
    cost_basis: float
    commission: float
    tax: float
    pnl: float
    is_manual_input: bool = False


@dataclass
class HoldingSummary:
    quantity: float
    avg_buy_price: float | None


def compute_holding_summary(trades: list["Trade"], key: TradeGroupKey) -> HoldingSummary:
    """보유 수량과 가중평균단가(WAC)를 한 번의 순회로 계산."""
    final_state = WalkerState(running_qty=0.0, running_cost=0.0)
    for ev in walk_trades(
        trades,
        group_filter=lambda t: is_same_group(t, key),
        sort_fn=sort_by_traded_at,
        track_fifo_lots=False,
    ):
        final_state = ev.state_after

    avg_buy_price = (
        final_state.running_cost / final_state.running_qty
        if final_state.running_qty > 0
        else None
    )
    return HoldingSummary(
        quantity=final_state.running_qty,
        avg_buy_price=avg_buy_price,
    )


def compute_flexible_breakdown(sell: "Trade") -> SellBreakdown:
    avg_cost_price = sell.avg_buy_price or 0.0
    quantity = sell.quantity
    sell_amount = sell.price * quantity
    cost_basis = avg_cost_price * quantity
    return SellBreakdown(
        sell_price=sell.price,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        sell_amount=sell_amount,
        cost_basis=cost_basis,
        commission=sell.commission,
        tax=sell.tax,
        pnl=sell.profit_loss or 0.0,
        is_manual_input=False,
    )
