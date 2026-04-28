"""거래 요약 집계 — computeSummary 등가."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import (
    RESULT_SUCCESS,
    STRATEGY_UNKNOWN,
    TAG_FEELING,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
)
from invest_note_api.domain.analysis.strategy_adherence import build_strategy_evaluations

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


@dataclass
class StrategyStats:
    type: str
    count: int
    result_count: int
    win_rate: float
    avg_pnl: float
    avg_holding_days: float


@dataclass
class EmotionStats:
    type: str
    count: int
    result_count: int
    win_rate: float
    avg_pnl: float


@dataclass
class TagStats:
    tag: str
    count: int
    win_rate: float
    avg_pnl: float


@dataclass
class StrategyAdherenceStats:
    type: str
    count: int
    result_count: int
    win_rate: float
    avg_pnl: float


@dataclass
class AnalysisSummary:
    total_trades: int
    sell_trades: int
    win_rate: float
    total_profit_loss: float
    by_strategy: list[StrategyStats] = field(default_factory=list)
    by_emotion: list[EmotionStats] = field(default_factory=list)
    by_tag: list[TagStats] = field(default_factory=list)
    missing_tag_rate: float = 0.0
    feeling_rate: float = 0.0
    reflection_rate: float = 0.0
    result_input_rate: float = 0.0
    strategy_adherence_rate: float = 0.0
    by_strategy_adherence: list[StrategyAdherenceStats] = field(default_factory=list)


def _win_rate(results: list[str]) -> float:
    return sum(1 for r in results if r == RESULT_SUCCESS) / len(results) * 100 if results else 0.0


def compute_summary(
    trades: list[Trade],
    pnl_map: dict[str, float],
    holding_days_map: dict[str, int],
) -> AnalysisSummary:
    sells = [t for t in trades if t.trade_type == TRADE_TYPE_SELL]
    buys = [t for t in trades if t.trade_type == TRADE_TYPE_BUY]

    sells_with_result = [t for t in sells if t.result is not None]
    win_count = sum(1 for t in sells_with_result if t.result == RESULT_SUCCESS)
    win_rate = (win_count / len(sells_with_result) * 100) if sells_with_result else 0.0
    total_profit_loss = sum(pnl_map.get(t.id, 0.0) for t in sells)

    strategy_evals = build_strategy_evaluations(trades, holding_days_map)

    # byStrategy — SELL에 저장된 계획 전략 기준
    strat_map: dict[str, dict] = {}
    for t in sells:
        evaluation = strategy_evals.get(t.id)
        key = (evaluation.planned if evaluation else t.strategy_type) or STRATEGY_UNKNOWN
        if key not in strat_map:
            strat_map[key] = {"pnls": [], "results": [], "days": []}
        s = strat_map[key]
        s["pnls"].append(pnl_map.get(t.id, 0.0))
        if t.result:
            s["results"].append(t.result)
        hd = evaluation.holding_days if evaluation else holding_days_map.get(t.id)
        if hd is not None:
            s["days"].append(hd)

    by_strategy = sorted(
        [
            StrategyStats(
                type=k,
                count=len(s["pnls"]),
                result_count=len(s["results"]),
                win_rate=_win_rate(s["results"]),
                avg_pnl=sum(s["pnls"]) / len(s["pnls"]) if s["pnls"] else 0.0,
                avg_holding_days=sum(s["days"]) / len(s["days"]) if s["days"] else 0.0,
            )
            for k, s in strat_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    adherence_map: dict[str, dict] = {}
    for t in sells:
        evaluation = strategy_evals.get(t.id)
        key = evaluation.adherence if evaluation else "UNKNOWN"
        if key not in adherence_map:
            adherence_map[key] = {"pnls": [], "results": []}
        a = adherence_map[key]
        a["pnls"].append(pnl_map.get(t.id, 0.0))
        if t.result:
            a["results"].append(t.result)

    adherence_order = {"FOLLOWED": 0, "DEVIATED": 1, "UNKNOWN": 2}
    by_strategy_adherence = sorted(
        [
            StrategyAdherenceStats(
                type=k,
                count=len(a["pnls"]),
                result_count=len(a["results"]),
                win_rate=_win_rate(a["results"]),
                avg_pnl=sum(a["pnls"]) / len(a["pnls"]) if a["pnls"] else 0.0,
            )
            for k, a in adherence_map.items()
        ],
        key=lambda x: adherence_order.get(x.type, 99),
    )
    period_sell_ids = {t.id for t in sells}
    judged = [
        e
        for sell_id, e in strategy_evals.items()
        if sell_id in period_sell_ids and e is not None and e.adherence != "UNKNOWN"
    ]
    followed = sum(1 for e in judged if e.adherence == "FOLLOWED")
    strategy_adherence_rate = followed / len(judged) * 100 if judged else 0.0

    # byEmotion — SELL의 저장된 emotion만 사용 (mutation 시 직전 BUY로부터 자동 산출됨)
    emotion_map: dict[str, dict] = {}
    for t in sells:
        if t.emotion is None:
            continue
        if t.emotion not in emotion_map:
            emotion_map[t.emotion] = {"pnls": [], "results": []}
        e = emotion_map[t.emotion]
        e["pnls"].append(pnl_map.get(t.id, 0.0))
        if t.result:
            e["results"].append(t.result)

    by_emotion = sorted(
        [
            EmotionStats(
                type=k,
                count=len(e["pnls"]),
                result_count=len(e["results"]),
                win_rate=_win_rate(e["results"]),
                avg_pnl=sum(e["pnls"]) / len(e["pnls"]) if e["pnls"] else 0.0,
            )
            for k, e in emotion_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # byTag — SELL의 저장된 reasoning_tags만 사용 (mutation 시 직전 BUY로부터 자동 산출됨)
    tag_map: dict[str, dict] = {}
    for sell in sells:
        for tag in sell.reasoning_tags or []:
            if tag not in tag_map:
                tag_map[tag] = {"pnls": [], "results": []}
            tm = tag_map[tag]
            tm["pnls"].append(pnl_map.get(sell.id, 0.0))
            if sell.result:
                tm["results"].append(sell.result)

    by_tag = sorted(
        [
            TagStats(
                tag=tag,
                count=len(tm["pnls"]),
                win_rate=_win_rate(tm["results"]),
                avg_pnl=sum(tm["pnls"]) / len(tm["pnls"]) if tm["pnls"] else 0.0,
            )
            for tag, tm in tag_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # 메타 지표
    missing_tag_rate = (
        sum(1 for t in buys if not t.reasoning_tags) / len(buys) * 100 if buys else 0.0
    )
    feeling_rate = (
        sum(1 for t in buys if TAG_FEELING in (t.reasoning_tags or [])) / len(buys) * 100 if buys else 0.0
    )
    reflection_rate = (
        sum(1 for t in sells if t.sell_reason and t.sell_reason.strip()) / len(sells) * 100
        if sells else 0.0
    )
    result_input_rate = len(sells_with_result) / len(sells) * 100 if sells else 0.0

    return AnalysisSummary(
        total_trades=len(trades),
        sell_trades=len(sells),
        win_rate=win_rate,
        total_profit_loss=total_profit_loss,
        by_strategy=by_strategy,
        by_emotion=by_emotion,
        by_tag=by_tag,
        missing_tag_rate=missing_tag_rate,
        feeling_rate=feeling_rate,
        reflection_rate=reflection_rate,
        result_input_rate=result_input_rate,
        strategy_adherence_rate=strategy_adherence_rate,
        by_strategy_adherence=by_strategy_adherence,
    )
