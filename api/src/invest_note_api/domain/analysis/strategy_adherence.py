"""전략 계획/실제/준수 평가."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from invest_note_api.domain.trade_types import (
    STRATEGY_LONG_TERM,
    STRATEGY_SCALPING,
    STRATEGY_SWING,
    STRATEGY_UNKNOWN,
    TRADE_TYPE_SELL,
)

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import StrategyType, Trade


StrategyAdherence = Literal["FOLLOWED", "DEVIATED", "UNKNOWN"]


@dataclass
class StrategyEvaluation:
    planned: "StrategyType | None"
    actual: "StrategyType"
    holding_days: int
    adherence: StrategyAdherence


def infer_actual_strategy(holding_days: int) -> "StrategyType":
    if holding_days <= 1:
        return STRATEGY_SCALPING
    if holding_days <= 30:
        return STRATEGY_SWING
    return STRATEGY_LONG_TERM


def build_strategy_evaluations(
    all_trades: list["Trade"],
    holding_days_map: dict[str, int] | None = None,
) -> dict[str, StrategyEvaluation]:
    """저장된 SELL strategy_type/holding_days로 전략 평가를 계산."""
    result: dict[str, StrategyEvaluation] = {}
    for trade in all_trades:
        if trade.trade_type != TRADE_TYPE_SELL:
            continue

        holding_days = trade.holding_days
        if holding_days is None and holding_days_map is not None:
            holding_days = holding_days_map.get(trade.id)
        if holding_days is None:
            continue

        planned = trade.strategy_type
        actual = infer_actual_strategy(holding_days)
        if not planned or planned == STRATEGY_UNKNOWN:
            adherence: StrategyAdherence = "UNKNOWN"
        else:
            adherence = "FOLLOWED" if planned == actual else "DEVIATED"

        result[trade.id] = StrategyEvaluation(
            planned=planned,
            actual=actual,
            holding_days=holding_days,
            adherence=adherence,
        )

    return result


def evaluate_strategy_for_sell(
    sell: "Trade",
    all_trades: list["Trade"],
    holding_days: int | None,
) -> StrategyEvaluation | None:
    _ = all_trades
    holding_days_map = {sell.id: holding_days} if holding_days is not None else None
    return build_strategy_evaluations([sell], holding_days_map).get(sell.id)
