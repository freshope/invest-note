from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, trade_country, trade_identifier
from invest_note_api.domain.trade_utils import MS_PER_DAY, to_kst

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade, StrategyType


@dataclass
class LotKey:
    ticker: str
    country: str
    account_id: str
    asset_name: str | None = None


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


def _is_flexible_match(
    trade: "Trade",
    target_country: str,
    target_ticker: str,
    target_asset: str,
    target_account_id: str,
) -> bool:
    if trade.account_id != target_account_id:
        return False
    if trade_country(trade) != target_country:
        return False
    trade_ticker = trade_identifier(trade)
    return trade_ticker == target_ticker or trade.asset_name == target_asset


def _sort_by_traded_at(trades: list["Trade"]) -> list["Trade"]:
    return sorted(trades, key=lambda t: t.traded_at)


def compute_lot_quantity(trades: list["Trade"], key: LotKey) -> float:
    lot_key = f"{key.ticker}:{key.country}:{key.account_id}"
    running_qty = 0.0

    for trade in _sort_by_traded_at(trades):
        trade_key = f"{trade_identifier(trade)}:{trade_country(trade)}:{trade.account_id}"
        if trade_key != lot_key:
            continue
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
        else:
            running_qty = max(0.0, running_qty - trade.quantity)

    return running_qty


def find_latest_buy_strategy(trades: list["Trade"], key: LotKey) -> "StrategyType | None":
    asset_name = key.asset_name or key.ticker
    buys = [
        t
        for t in trades
        if t.trade_type == TRADE_TYPE_BUY
        and _is_flexible_match(t, key.country, key.ticker, asset_name, key.account_id)
    ]
    buys.sort(key=lambda t: t.traded_at, reverse=True)
    return buys[0].strategy_type if buys else None


def compute_total_holding(
    trades: list["Trade"],
    ticker: str | None,
    asset_name: str,
    country: str,
    account_id: str,
) -> float:
    target_ticker = ticker or asset_name

    running_qty = 0.0
    for trade in _sort_by_traded_at(trades):
        if not _is_flexible_match(trade, country, target_ticker, asset_name, account_id):
            continue
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
        else:
            running_qty = max(0.0, running_qty - trade.quantity)

    return running_qty


def compute_wac(
    trades: list["Trade"],
    ticker: str | None,
    asset_name: str,
    country: str,
    account_id: str,
) -> float | None:
    """가중평균단가(WAC) 계산. 보유 수량이 없으면 None."""
    target_ticker = ticker or asset_name
    running_qty = 0.0
    running_cost = 0.0

    for trade in _sort_by_traded_at(trades):
        if not _is_flexible_match(trade, country, target_ticker, asset_name, account_id):
            continue
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
            running_cost += trade.price * trade.quantity
        else:
            avg_cost = running_cost / running_qty if running_qty > 0 else 0.0
            matched = min(trade.quantity, running_qty)
            running_cost = max(0.0, running_cost - avg_cost * matched)
            running_qty = max(0.0, running_qty - matched)

    return running_cost / running_qty if running_qty > 0 else None


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
    target_country = trade_country(sell)
    target_ticker = trade_identifier(sell)
    target_asset = sell.asset_name
    target_account_id = sell.account_id
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

        if not _is_flexible_match(trade, target_country, target_ticker, target_asset, target_account_id):
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
