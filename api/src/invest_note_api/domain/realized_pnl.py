from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    STRATEGY_UNKNOWN,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    StrategyType,
    Trade,
)
from invest_note_api.domain.trade_utils import MS_PER_DAY, to_kst


@dataclass(frozen=True)
class TradeGroupKey:
    ticker: str | None
    asset_name: str
    country: str
    account_id: str


MutationType = Literal["insert", "update", "delete"]


def trade_to_group_key(trade: Trade) -> TradeGroupKey:
    return TradeGroupKey(
        ticker=trade.ticker_symbol,
        asset_name=trade.asset_name,
        country=trade.country_code or DEFAULT_COUNTRY,
        account_id=trade.account_id,
    )


def _is_same_group(trade: Trade, key: TradeGroupKey) -> bool:
    if trade.account_id != key.account_id:
        return False
    if (trade.country_code or DEFAULT_COUNTRY) != key.country:
        return False
    trade_ticker = trade.ticker_symbol or trade.asset_name
    target_ticker = key.ticker or key.asset_name
    return trade_ticker == target_ticker


def sort_for_calc(trades: list[Trade]) -> list[Trade]:
    """traded_at 오름차순, 동시각은 BUY 먼저, 그 다음 created_at."""
    return sorted(
        trades,
        key=lambda t: (
            t.traded_at,
            0 if t.trade_type == TRADE_TYPE_BUY else 1,
            t.created_at,
        ),
    )


def _sell_pnl(trade: Trade, avg_cost: float, cost_qty: float | None = None) -> float:
    qty = cost_qty if cost_qty is not None else trade.quantity
    return trade.price * qty - avg_cost * qty - trade.commission - trade.tax


@dataclass
class GroupPnLEntry:
    profit_loss: float
    avg_buy_price: float
    holding_days: int | None
    strategy_type: StrategyType | None
    matched_qty: float
    running_qty_after: float


def _strategy_from_consumed(consumed: list[tuple[StrategyType | None, float, int]]) -> StrategyType | None:
    if not consumed:
        return None

    by_strategy: dict[str, dict] = {}
    for strategy, qty, order in consumed:
        key = strategy or STRATEGY_UNKNOWN
        if key not in by_strategy:
            by_strategy[key] = {"qty": 0.0, "order": order}
        by_strategy[key]["qty"] += qty
        by_strategy[key]["order"] = min(by_strategy[key]["order"], order)

    selected = sorted(by_strategy.items(), key=lambda item: (-item[1]["qty"], item[1]["order"]))[0][0]
    return selected  # type: ignore[return-value]


def compute_group_pnl(trades: list[Trade], key: TradeGroupKey) -> dict[str, GroupPnLEntry]:
    """그룹 내 SELL 거래별 WAC PnL 계산."""
    group = sort_for_calc([t for t in trades if _is_same_group(t, key)])

    result: dict[str, GroupPnLEntry] = {}
    running_qty = 0.0
    running_cost = 0.0
    fifo_lots: list[dict] = []
    buy_order = 0

    for trade in group:
        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
            running_cost += trade.price * trade.quantity
            fifo_lots.append({
                "qty": trade.quantity,
                "time_ms": int(to_kst(trade.traded_at).timestamp() * 1000),
                "strategy": trade.strategy_type,
                "order": buy_order,
            })
            buy_order += 1
        else:
            avg_cost = running_cost / running_qty if running_qty > 0 else 0.0
            matched_qty = min(trade.quantity, running_qty)
            remaining = trade.quantity
            sell_time_ms = int(to_kst(trade.traded_at).timestamp() * 1000)
            weighted_ms = 0.0
            total_consumed = 0.0
            consumed: list[tuple[StrategyType | None, float, int]] = []
            while remaining > 0 and fifo_lots:
                slot = fifo_lots[0]
                consume = min(slot["qty"], remaining)
                weighted_ms += (sell_time_ms - slot["time_ms"]) * consume
                total_consumed += consume
                consumed.append((slot["strategy"], consume, slot["order"]))
                slot["qty"] -= consume
                remaining -= consume
                if slot["qty"] <= 0:
                    fifo_lots.pop(0)
            holding_days = (
                math.floor(weighted_ms / total_consumed / MS_PER_DAY + 0.5)
                if total_consumed > 0
                else None
            )
            result[trade.id] = GroupPnLEntry(
                profit_loss=_sell_pnl(trade, avg_cost, matched_qty),
                avg_buy_price=avg_cost,
                holding_days=holding_days,
                strategy_type=_strategy_from_consumed(consumed),
                matched_qty=matched_qty,
                running_qty_after=max(0.0, running_qty - trade.quantity),
            )
            running_cost = max(0.0, running_cost - avg_cost * matched_qty)
            running_qty = max(0.0, running_qty - trade.quantity)

    return result


def validate_mutation(
    trades: list[Trade],
    mutation_type: MutationType,
    trade: Trade,
    patch: dict | None = None,
) -> tuple[bool, str, list[str]]:
    """
    가상 적용 후 oversell 여부 검증.

    Returns:
        (ok, message, affected_sell_ids)
    """
    if mutation_type == "insert":
        virtual = [*trades, trade]
    elif mutation_type == "update":
        patched_data = {**trade.model_dump(), **(patch or {})}
        patched = Trade(**patched_data)
        virtual = [patched if t.id == trade.id else t for t in trades]
    else:  # delete
        virtual = [t for t in trades if t.id != trade.id]

    key = trade_to_group_key(trade)
    group = sort_for_calc([t for t in virtual if _is_same_group(t, key)])

    running_qty = 0.0
    running_cost = 0.0
    affected_sell_ids: list[str] = []

    for t in group:
        if t.trade_type == TRADE_TYPE_BUY:
            running_qty += t.quantity
            running_cost += t.price * t.quantity
        else:
            if running_qty <= 0:
                return False, "보유 수량이 없어 매도할 수 없습니다.", []
            if t.quantity > running_qty:
                return False, "보유 수량이 부족한 매도 거래가 생깁니다.", []
            avg_cost = running_cost / running_qty
            matched_qty = min(t.quantity, running_qty)
            affected_sell_ids.append(t.id)
            running_cost = max(0.0, running_cost - avg_cost * matched_qty)
            running_qty = max(0.0, running_qty - t.quantity)

    return True, "", affected_sell_ids


def build_pnl_map(trades: list[Trade]) -> dict[str, float]:
    """저장된 profit_loss 값으로 SELL id → PnL 맵 구성."""
    return {t.id: float(t.profit_loss or 0) for t in trades if t.trade_type == TRADE_TYPE_SELL}
