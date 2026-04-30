from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    is_same_group,
    trade_to_group_key,
)
from invest_note_api.domain.trade_types import TRADE_TYPE_BUY
from invest_note_api.domain.trade_utils import MS_PER_DAY, to_kst

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade, StrategyType


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


def compute_lot_quantity(trades: list["Trade"], key: TradeGroupKey) -> float:
    running_qty = 0.0

    for trade in _sort_by_traded_at(trades):
        if not is_same_group(trade, key):
            continue
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
        else:
            running_qty = max(0.0, running_qty - trade.quantity)

    return running_qty


def find_latest_buy_strategy(trades: list["Trade"], key: TradeGroupKey) -> "StrategyType | None":
    buys = [
        t
        for t in trades
        if t.trade_type == TRADE_TYPE_BUY and is_same_group(t, key)
    ]
    buys.sort(key=lambda t: t.traded_at, reverse=True)
    return buys[0].strategy_type if buys else None


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


def compute_flexible_holding_days(sell: "Trade", all_trades: list["Trade"]) -> int | None:
    """FIFO 가중평균 보유일수 계산."""
    key = trade_to_group_key(sell)
    sell_time_ms = int(to_kst(sell.traded_at).timestamp() * 1000)

    queue: list[dict] = []  # [{qty, time_ms}]

    for trade in _sort_by_traded_at(all_trades):
        if trade.id == sell.id:
            remaining = sell.quantity
            weighted_ms = 0.0
            total_consumed = 0.0

            for slot in queue:
                if remaining <= 0:
                    break
                consume = min(slot["qty"], remaining)
                weighted_ms += (sell_time_ms - slot["time_ms"]) * consume
                total_consumed += consume
                remaining -= consume

            if total_consumed > 0:
                return math.floor(weighted_ms / total_consumed / MS_PER_DAY + 0.5)
            return None

        if not is_same_group(trade, key):
            continue

        if trade.trade_type == TRADE_TYPE_BUY:
            queue.append({"qty": trade.quantity, "time_ms": int(to_kst(trade.traded_at).timestamp() * 1000)})
        else:
            rem = trade.quantity
            while rem > 0 and queue:
                consume = min(queue[0]["qty"], rem)
                queue[0]["qty"] -= consume
                rem -= consume
                if queue[0]["qty"] <= 0:
                    queue.pop(0)

    return None
