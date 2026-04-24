"""analysis 라우터 — summary / behavior / suggestions."""
from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query
from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.trades_repo import list_trades
from invest_note_api.domain.analysis.aggregate import compute_summary
from invest_note_api.domain.analysis.concentration import compute_concentration
from invest_note_api.domain.analysis.holding_period import compute_holding_days_map
from invest_note_api.domain.analysis.period import DEFAULT_PERIOD, filter_by_period, parse_period
from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL
from invest_note_api.domain.analysis.profile import compute_profile
from invest_note_api.domain.analysis.rules import evaluate_rules
from invest_note_api.domain.portfolio import build_positions, merge_quotes
from invest_note_api.domain.realized_pnl import build_pnl_map
from invest_note_api.external.quotes import fetch_quotes_by_keys

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis")

_HOLDING_BUCKETS: list[dict] = [
    {"label": "1일 이내", "max_days": 1},
    {"label": "1주 이내", "max_days": 7},
    {"label": "1개월 이내", "max_days": 30},
    {"label": "3개월 이내", "max_days": 90},
    {"label": "6개월 이내", "max_days": 180},
    {"label": "1년 이내", "max_days": 365},
    {"label": "1년 이상", "max_days": float("inf")},
]
_HOLDING_ORDER = [b["label"] for b in _HOLDING_BUCKETS]

_SIZE_ORDER = ["50만 미만", "50~100만", "100~500만", "500만~1천만", "1천~5천만", "5천만 이상"]


def _holding_bucket(days: int) -> str:
    for b in _HOLDING_BUCKETS:
        if days <= b["max_days"]:
            return b["label"]
    return _HOLDING_BUCKETS[-1]["label"]


def _size_bucket(amount: float) -> str:
    if amount < 500_000:
        return "50만 미만"
    if amount < 1_000_000:
        return "50~100만"
    if amount < 5_000_000:
        return "100~500만"
    if amount < 10_000_000:
        return "500만~1천만"
    if amount < 50_000_000:
        return "1천~5천만"
    return "5천만 이상"


async def _get_trades_context(period_str: str, user_id: str, pool: asyncpg.Pool):
    """공통 컨텍스트: (all_trades, trades, period)."""
    async with acquire_for_user(pool, user_id) as conn:
        all_trades = await list_trades(conn, user_id)
    period = parse_period(period_str)
    trades = filter_by_period(all_trades, period)
    return all_trades, trades, period


@router.get("/summary")
async def get_analysis_summary(
    period: str = Query(default=DEFAULT_PERIOD),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    all_trades, trades, period_val = await _get_trades_context(period, user.id, pool)

    pnl_map = build_pnl_map(all_trades)
    holding_days_map = compute_holding_days_map(all_trades)
    summary = compute_summary(trades, pnl_map, holding_days_map, all_trades)

    return {
        "period": period_val,
        "totalTrades": summary.total_trades,
        "sellTrades": summary.sell_trades,
        "winRate": summary.win_rate,
        "totalProfitLoss": summary.total_profit_loss,
        "byStrategy": [
            {
                "type": s.type,
                "count": s.count,
                "resultCount": s.result_count,
                "winRate": s.win_rate,
                "avgPnL": s.avg_pnl,
                "avgHoldingDays": s.avg_holding_days,
            }
            for s in summary.by_strategy
        ],
        "byEmotion": [
            {
                "type": e.type,
                "count": e.count,
                "sellCount": e.sell_count,
                "resultCount": e.result_count,
                "winRate": e.win_rate,
                "avgPnL": e.avg_pnl,
            }
            for e in summary.by_emotion
        ],
        "byTag": [
            {
                "tag": t.tag,
                "count": t.count,
                "winRate": t.win_rate,
                "avgPnL": t.avg_pnl,
            }
            for t in summary.by_tag
        ],
        "missingTagRate": summary.missing_tag_rate,
        "feelingRate": summary.feeling_rate,
        "reflectionRate": summary.reflection_rate,
        "resultInputRate": summary.result_input_rate,
    }


@router.get("/behavior")
async def get_analysis_behavior(
    period: str = Query(default=DEFAULT_PERIOD),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    all_trades, trades, period_val = await _get_trades_context(period, user.id, pool)

    positions0 = build_positions(all_trades)
    positions = positions0
    try:
        quotes = await fetch_quotes_by_keys([p.key for p in positions0])
        positions = merge_quotes(positions0, quotes)
    except Exception as e:
        logger.warning("시세 fetch 실패, cost_basis fallback: %s", e)

    concentration = compute_concentration(positions, all_trades)
    all_holding_days_map = compute_holding_days_map(all_trades)
    profile, input_rates = compute_profile(trades, concentration.hhi, all_holding_days_map)

    period_sell_ids = {t.id for t in trades if t.trade_type == TRADE_TYPE_SELL}
    holding_dist: dict[str, int] = {}
    for tid, days in all_holding_days_map.items():
        if tid not in period_sell_ids:
            continue
        b = _holding_bucket(days)
        holding_dist[b] = holding_dist.get(b, 0) + 1
    holding_period_dist = [
        {"bucket": b, "count": holding_dist[b]}
        for b in _HOLDING_ORDER
        if b in holding_dist
    ]

    size_dist: dict[str, int] = {}
    for t in trades:
        if t.trade_type == TRADE_TYPE_BUY:
            b = _size_bucket(t.total_amount)
            size_dist[b] = size_dist.get(b, 0) + 1
    position_size_dist = [
        {"bucket": b, "count": size_dist[b]}
        for b in _SIZE_ORDER
        if b in size_dist
    ]

    return {
        "period": period_val,
        "profile": {
            "tempo": profile.tempo,
            "diversification": profile.diversification,
            "emotionStability": profile.emotion_stability,
            "reasoningQuality": profile.reasoning_quality,
            "reviewHabit": profile.review_habit,
        },
        "inputRates": {
            "holdingDays": input_rates.holding_days,
            "emotion": input_rates.emotion,
            "reasoningTag": input_rates.reasoning_tag,
            "result": input_rates.result,
            "reflection": input_rates.reflection,
        },
        "holdingPeriodDist": holding_period_dist,
        "positionSizeDist": position_size_dist,
        "concentration": {
            "hhi": concentration.hhi,
            "top3": concentration.top3,
            "byCountry": concentration.by_country,
            "byMarket": concentration.by_market,
        },
    }


@router.get("/suggestions")
async def get_analysis_suggestions(
    period: str = Query(default=DEFAULT_PERIOD),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    all_trades, trades, period_val = await _get_trades_context(period, user.id, pool)

    positions = build_positions(all_trades)
    concentration = compute_concentration(positions, all_trades)
    pnl_map = build_pnl_map(all_trades)
    holding_days_map = compute_holding_days_map(all_trades)
    summary = compute_summary(trades, pnl_map, holding_days_map, all_trades)
    profile, _ = compute_profile(trades, concentration.hhi, holding_days_map)

    suggestions = evaluate_rules({"summary": summary, "profile": profile, "concentration": concentration})

    return {
        "period": period_val,
        "suggestions": [
            {
                "id": s.id,
                "severity": s.severity,
                "title": s.title,
                "body": s.body,
                **({"metric": s.metric} if s.metric is not None else {}),
                **({"linkSection": s.link_section} if s.link_section is not None else {}),
            }
            for s in suggestions
        ],
    }
