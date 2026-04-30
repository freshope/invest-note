from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    is_same_group,
)
from invest_note_api.domain.trade_types import TRADE_TYPE_BUY

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


def _sort_by_traded_at(trades: list["Trade"]) -> list["Trade"]:
    return sorted(trades, key=lambda t: t.traded_at)


def compute_holding_summary(trades: list["Trade"], key: TradeGroupKey) -> HoldingSummary:
    """보유 수량과 가중평균단가(WAC)를 한 번의 순회로 계산."""
    running_qty = 0.0
    running_cost = 0.0
    for trade in _sort_by_traded_at(trades):
        if not is_same_group(trade, key):
            continue
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
            running_cost += trade.price * trade.quantity
        else:
            avg_cost = running_cost / running_qty if running_qty > 0 else 0.0
            matched = min(trade.quantity, running_qty)
            running_cost = max(0.0, running_cost - avg_cost * matched)
            running_qty = max(0.0, running_qty - matched)

    avg_buy_price = running_cost / running_qty if running_qty > 0 else None
    return HoldingSummary(quantity=running_qty, avg_buy_price=avg_buy_price)


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
