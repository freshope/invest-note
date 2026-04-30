from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
from typing import Literal

from invest_note_api.domain.trade_types import (
    RESULT_BREAKEVEN,
    RESULT_FAIL,
    RESULT_SUCCESS,
    STRATEGY_UNKNOWN,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    EmotionType,
    ReasoningTag,
    StrategyType,
    Trade,
    TradeResult,
    trade_country,
    trade_identifier,
)
from invest_note_api.domain.trade_utils import MS_PER_DAY, to_kst_ms
from invest_note_api.domain.trade_walker import (
    ConsumedLot,
    walk_trades,
)


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
        country=trade_country(trade),
        account_id=trade.account_id,
    )


def is_same_group(trade: Trade, key: TradeGroupKey) -> bool:
    if trade.account_id != key.account_id:
        return False
    if trade_country(trade) != key.country:
        return False
    trade_ticker = trade_identifier(trade)
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
    reasoning_tags: list[ReasoningTag]
    emotion: EmotionType | None
    result: TradeResult
    matched_qty: float
    running_qty_after: float


def derive_result_from_pnl(pnl: float) -> TradeResult:
    if pnl > 0:
        return RESULT_SUCCESS
    if pnl < 0:
        return RESULT_FAIL
    return RESULT_BREAKEVEN


def _strategy_from_consumed(consumed: Sequence[ConsumedLot]) -> StrategyType | None:
    if not consumed:
        return None

    by_strategy: dict[str, dict] = {}
    for c in consumed:
        key = c.lot.strategy or STRATEGY_UNKNOWN
        if key not in by_strategy:
            by_strategy[key] = {"qty": 0.0, "order": c.lot.order}
        by_strategy[key]["qty"] += c.qty
        by_strategy[key]["order"] = min(by_strategy[key]["order"], c.lot.order)

    selected = sorted(by_strategy.items(), key=lambda item: (-item[1]["qty"], item[1]["order"]))[0][0]
    return selected  # type: ignore[return-value]


def _meta_from_consumed_latest(
    consumed: Sequence[ConsumedLot],
) -> tuple[list[ReasoningTag], EmotionType | None]:
    """소비된 BUY lot 중 가장 최근(time_ms 최대, 동률 시 order 최대)의 tags/emotion."""
    if not consumed:
        return [], None
    latest = max(consumed, key=lambda c: (c.lot.time_ms, c.lot.order))
    return list(latest.lot.reasoning_tags), latest.lot.emotion


def _holding_days_from_consumed(
    consumed: Sequence[ConsumedLot], sell_time_ms: int
) -> int | None:
    total = sum(c.qty for c in consumed)
    if total <= 0:
        return None
    weighted_ms = sum((sell_time_ms - c.lot.time_ms) * c.qty for c in consumed)
    return math.floor(weighted_ms / total / MS_PER_DAY + 0.5)


def compute_group_pnl(trades: list[Trade], key: TradeGroupKey) -> dict[str, GroupPnLEntry]:
    """그룹 내 SELL 거래별 WAC PnL 계산."""
    result: dict[str, GroupPnLEntry] = {}

    for ev in walk_trades(
        trades,
        group_filter=lambda t: is_same_group(t, key),
        sort_fn=sort_for_calc,
    ):
        if ev.kind != "SELL":
            continue

        sell_time_ms = to_kst_ms(ev.trade.traded_at)
        avg_cost = ev.state_before.avg_cost
        pnl = _sell_pnl(ev.trade, avg_cost, ev.matched_qty)
        tags, emotion = _meta_from_consumed_latest(ev.consumed)

        result[ev.trade.id] = GroupPnLEntry(
            profit_loss=pnl,
            avg_buy_price=avg_cost,
            holding_days=_holding_days_from_consumed(ev.consumed, sell_time_ms),
            strategy_type=_strategy_from_consumed(ev.consumed),
            reasoning_tags=tags,
            emotion=emotion,
            result=derive_result_from_pnl(pnl),
            matched_qty=ev.matched_qty,
            running_qty_after=ev.state_after.running_qty,
        )

    return result


def _apply_virtual(
    trades: list[Trade],
    mutation_type: MutationType,
    trade: Trade,
    patch: dict | None,
) -> list[Trade]:
    if mutation_type == "insert":
        return [*trades, trade]
    if mutation_type == "update":
        patched_data = {**trade.model_dump(), **(patch or {})}
        patched = Trade(**patched_data)
        return [patched if t.id == trade.id else t for t in trades]
    return [t for t in trades if t.id != trade.id]


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
    virtual = _apply_virtual(trades, mutation_type, trade, patch)
    key = trade_to_group_key(trade)
    affected_sell_ids: list[str] = []

    for ev in walk_trades(
        virtual,
        group_filter=lambda t: is_same_group(t, key),
        sort_fn=sort_for_calc,
        track_fifo_lots=False,
    ):
        if ev.kind != "SELL":
            continue
        if ev.no_holding:
            return False, "보유 수량이 없어 매도할 수 없습니다.", []
        if ev.oversell:
            return False, "보유 수량이 부족한 매도 거래가 생깁니다.", []
        affected_sell_ids.append(ev.trade.id)

    return True, "", affected_sell_ids


def build_pnl_map(trades: list[Trade]) -> dict[str, float]:
    """저장된 profit_loss 값으로 SELL id → PnL 맵 구성."""
    return {t.id: float(t.profit_loss or 0) for t in trades if t.trade_type == TRADE_TYPE_SELL}
