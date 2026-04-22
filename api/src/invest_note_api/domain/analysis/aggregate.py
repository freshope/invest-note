"""거래 요약 집계 — computeSummary 등가."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    sell_count: int
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


def compute_summary(
    trades: list[Trade],
    pnl_map: dict[str, float],
    holding_days_map: dict[str, int],
    all_trades: list[Trade] | None = None,
) -> AnalysisSummary:
    sells = [t for t in trades if t.trade_type == "SELL"]
    buys = [t for t in trades if t.trade_type == "BUY"]

    sells_with_result = [t for t in sells if t.result is not None]
    win_count = sum(1 for t in sells_with_result if t.result == "SUCCESS")
    win_rate = (win_count / len(sells_with_result) * 100) if sells_with_result else 0.0
    total_profit_loss = sum(pnl_map.get(t.id, 0.0) for t in sells)

    # byStrategy
    strat_map: dict[str, dict] = {}
    for t in sells:
        key = t.strategy_type or "UNKNOWN"
        if key not in strat_map:
            strat_map[key] = {"pnls": [], "results": [], "days": []}
        s = strat_map[key]
        s["pnls"].append(pnl_map.get(t.id, 0.0))
        if t.result:
            s["results"].append(t.result)
        hd = holding_days_map.get(t.id)
        if hd is not None:
            s["days"].append(hd)

    by_strategy = sorted(
        [
            StrategyStats(
                type=k,
                count=len(s["pnls"]),
                result_count=len(s["results"]),
                win_rate=(
                    sum(1 for r in s["results"] if r == "SUCCESS") / len(s["results"]) * 100
                    if s["results"] else 0.0
                ),
                avg_pnl=sum(s["pnls"]) / len(s["pnls"]) if s["pnls"] else 0.0,
                avg_holding_days=sum(s["days"]) / len(s["days"]) if s["days"] else 0.0,
            )
            for k, s in strat_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # byEmotion
    emotion_map: dict[str, dict] = {}
    for t in trades:
        if t.emotion is None:
            continue
        if t.emotion not in emotion_map:
            emotion_map[t.emotion] = {"total_count": 0, "sell_count": 0, "pnls": [], "results": []}
        e = emotion_map[t.emotion]
        e["total_count"] += 1
        if t.trade_type == "SELL":
            e["sell_count"] += 1
            e["pnls"].append(pnl_map.get(t.id, 0.0))
            if t.result:
                e["results"].append(t.result)

    by_emotion = sorted(
        [
            EmotionStats(
                type=k,
                count=e["total_count"],
                sell_count=e["sell_count"],
                result_count=len(e["results"]),
                win_rate=(
                    sum(1 for r in e["results"] if r == "SUCCESS") / len(e["results"]) * 100
                    if e["results"] else 0.0
                ),
                avg_pnl=sum(e["pnls"]) / len(e["pnls"]) if e["pnls"] else 0.0,
            )
            for k, e in emotion_map.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # byTag — 기간 밖 BUY도 포함 (allTrades 기준), 계좌별 분리
    all_buys = sorted(
        [t for t in (all_trades or trades) if t.trade_type == "BUY"],
        key=lambda t: (t.traded_at, 0),  # BUY-first tie-break (BUY=0 < SELL=1)
    )
    buys_by_key: dict[str, list[Trade]] = {}
    for t in all_buys:
        key = f"{t.ticker_symbol or t.asset_name}:{t.country_code or 'KR'}:{t.account_id}"
        buys_by_key.setdefault(key, []).append(t)

    tag_map: dict[str, dict] = {}
    for sell in sells:
        key = f"{sell.ticker_symbol or sell.asset_name}:{sell.country_code or 'KR'}:{sell.account_id}"
        buys_for_key = buys_by_key.get(key, [])
        prev_buys = [b for b in buys_for_key if b.traded_at <= sell.traded_at]
        tags = prev_buys[-1].reasoning_tags if prev_buys else []
        if not tags:
            continue
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
                win_rate=(
                    sum(1 for r in tm["results"] if r == "SUCCESS") / len(tm["results"]) * 100
                    if tm["results"] else 0.0
                ),
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
        sum(1 for t in buys if "FEELING" in (t.reasoning_tags or [])) / len(buys) * 100 if buys else 0.0
    )
    reflection_rate = (
        sum(1 for t in sells if t.reflection_note and t.reflection_note.strip()) / len(sells) * 100
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
    )
