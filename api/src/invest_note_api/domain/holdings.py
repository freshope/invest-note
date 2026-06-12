from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    is_same_group,
    sort_for_calc,
)
from invest_note_api.domain.trade_types import krw_normalized_trade
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
        sort_fn=sort_for_calc,
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
    # KRW 정규화(price/commission/tax ×거래시점 환율) — avg_buy_price/profit_loss 는 이미 KRW.
    # 매도금액(KRW)과 매수원가(KRW)를 같은 통화로 맞춰 breakdown 일관성 유지.
    s = krw_normalized_trade(sell)
    avg_cost_price = s.avg_buy_price or 0.0
    quantity = s.quantity
    sell_amount = s.price * quantity
    cost_basis = avg_cost_price * quantity
    return SellBreakdown(
        sell_price=s.price,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        sell_amount=sell_amount,
        cost_basis=cost_basis,
        commission=s.commission,
        tax=s.tax,
        pnl=s.profit_loss or 0.0,
    )
