"""거래 요약 집계 — computeSummary 등가."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from invest_note_api.domain.analysis._math import _percent
from invest_note_api.domain.analysis.strategy_adherence import (
    ADHERENCE_DEVIATED,
    ADHERENCE_FOLLOWED,
    ADHERENCE_UNKNOWN,
    build_strategy_evaluations,
)
from invest_note_api.domain.trade_types import (
    EMOTION_UNTAGGED,
    RESULT_SUCCESS,
    STRATEGY_UNKNOWN,
    TAG_FEELING,
    TAG_UNTAGGED,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    EmotionBucket,
    ReasoningTagBucket,
)

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


@dataclass
class StrategyStats:
    type: str
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float
    avg_holding_days: float


@dataclass
class EmotionStats:
    type: EmotionBucket
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float


@dataclass
class TagStats:
    tag: ReasoningTagBucket
    count: int
    win_rate: float
    sum_pnl: float


@dataclass
class StrategyAdherenceStats:
    type: str
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float


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
    return _percent(sum(1 for r in results if r == RESULT_SUCCESS), len(results))


def compute_summary(
    trades: list[Trade],
    pnl_map: dict[str, float],
    holding_days_map: dict[str, int],
) -> AnalysisSummary:
    """trades, pnl_map, holding_days_map은 모두 동일 period 범위에서 빌드된 입력이어야 한다."""
    sells = [t for t in trades if t.trade_type == TRADE_TYPE_SELL]
    buys = [t for t in trades if t.trade_type == TRADE_TYPE_BUY]

    sells_with_result = [t for t in sells if t.result is not None]
    win_count = sum(1 for t in sells_with_result if t.result == RESULT_SUCCESS)
    win_rate = _percent(win_count, len(sells_with_result))
    total_profit_loss = sum(pnl_map.get(t.id, 0.0) for t in sells)

    # period-filtered trades 입력 — 기간별 strat_map/adherence_map 스냅샷 용
    strategy_evals = build_strategy_evaluations(trades, holding_days_map)

    # byStrategy — SELL에 저장된 전략 기준
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
                sum_pnl=sum(s["pnls"]),
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
        key = evaluation.adherence if evaluation else ADHERENCE_UNKNOWN
        if key not in adherence_map:
            adherence_map[key] = {"pnls": [], "results": []}
        a = adherence_map[key]
        a["pnls"].append(pnl_map.get(t.id, 0.0))
        if t.result:
            a["results"].append(t.result)

    adherence_order = {ADHERENCE_FOLLOWED: 0, ADHERENCE_DEVIATED: 1, ADHERENCE_UNKNOWN: 2}
    by_strategy_adherence = sorted(
        [
            StrategyAdherenceStats(
                type=k,
                count=len(a["pnls"]),
                result_count=len(a["results"]),
                win_rate=_win_rate(a["results"]),
                sum_pnl=sum(a["pnls"]),
            )
            for k, a in adherence_map.items()
        ],
        key=lambda x: adherence_order.get(x.type, 99),
    )
    period_sell_ids = {t.id for t in sells}
    judged = [
        e
        for sell_id, e in strategy_evals.items()
        if sell_id in period_sell_ids and e is not None and e.adherence != ADHERENCE_UNKNOWN
    ]
    followed = sum(1 for e in judged if e.adherence == ADHERENCE_FOLLOWED)
    strategy_adherence_rate = _percent(followed, len(judged))

    # byEmotion — emotion 미입력 SELL은 EMOTION_UNTAGGED 버킷으로 모음.
    # 합계가 totalProfitLoss와 일치하려면 누락 거래도 어딘가에는 포함되어야 함.
    emotion_map: dict[EmotionBucket, dict] = {}
    for t in sells:
        key: EmotionBucket = t.emotion or EMOTION_UNTAGGED
        if key not in emotion_map:
            emotion_map[key] = {"pnls": [], "results": []}
        e = emotion_map[key]
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
                sum_pnl=sum(e["pnls"]),
            )
            for k, e in emotion_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # byTag — reasoning_tags 미입력 SELL은 TAG_UNTAGGED 단일 버킷으로 모음.
    # 다중 태그 거래는 각 태그 버킷에 PnL이 중복 합산되므로 byTag 합계는
    # totalProfitLoss와 정확히 일치하지 않을 수 있음 (FE에서 안내 제공).
    tag_map: dict[ReasoningTagBucket, dict] = {}
    for sell in sells:
        tags: list[ReasoningTagBucket] = list(sell.reasoning_tags) or [TAG_UNTAGGED]
        for tag in tags:
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
                sum_pnl=sum(tm["pnls"]),
            )
            for tag, tm in tag_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # 메타 지표
    missing_tag_rate = _percent(
        sum(1 for t in buys if not t.reasoning_tags), len(buys)
    )
    feeling_rate = _percent(
        sum(1 for t in buys if TAG_FEELING in (t.reasoning_tags or [])), len(buys)
    )
    reflection_rate = _percent(
        sum(1 for t in sells if t.sell_reason and t.sell_reason.strip()), len(sells)
    )
    result_input_rate = _percent(len(sells_with_result), len(sells))

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
