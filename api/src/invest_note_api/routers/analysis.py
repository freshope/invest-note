"""analysis 라우터 — dashboard 단일 엔드포인트."""
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
from invest_note_api.domain.analysis.profile import compute_profile
from invest_note_api.domain.analysis.rules import evaluate_rules
from invest_note_api.domain.analysis.strategy_adherence import build_strategy_evaluations
from invest_note_api.domain.portfolio import build_positions, merge_quotes
from invest_note_api.domain.realized_pnl import build_pnl_map
from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL
from invest_note_api.external.quotes import fetch_quotes_by_keys
from invest_note_api.schemas.analysis_response import AnalysisDashboardResponse

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


@router.get(
    "/dashboard",
    response_model=AnalysisDashboardResponse,
    response_model_exclude_none=True,
)
async def get_analysis_dashboard(
    period: str = Query(default=DEFAULT_PERIOD),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> AnalysisDashboardResponse:
    async with acquire_for_user(pool, user.id) as conn:
        all_trades = await list_trades(conn, user.id)
    period_val = parse_period(period)
    trades = filter_by_period(all_trades, period_val)

    pnl_map = build_pnl_map(all_trades)
    holding_days_map = compute_holding_days_map(all_trades)
    positions0 = build_positions(all_trades)

    positions = positions0
    try:
        quotes = await fetch_quotes_by_keys([p.key for p in positions0])
        positions = merge_quotes(positions0, quotes)
    except Exception as e:
        logger.warning("시세 fetch 실패, cost_basis fallback: %s", e)

    concentration = compute_concentration(positions, all_trades)
    summary = compute_summary(trades, pnl_map, holding_days_map)
    strategy_evals = build_strategy_evaluations(all_trades, holding_days_map)
    profile, input_rates = compute_profile(trades, holding_days_map, strategy_evals)
    suggestions = evaluate_rules(
        {"summary": summary, "profile": profile, "concentration": concentration}
    )

    period_sell_ids = {t.id for t in trades if t.trade_type == TRADE_TYPE_SELL}
    holding_dist: dict[str, int] = {}
    for tid, days in holding_days_map.items():
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

    return AnalysisDashboardResponse.model_validate({
        "period": period_val,
        "summary": {
            "period": period_val,
            "total_trades": summary.total_trades,
            "sell_trades": summary.sell_trades,
            "win_rate": summary.win_rate,
            "total_profit_loss": summary.total_profit_loss,
            "by_strategy": summary.by_strategy,
            "by_emotion": summary.by_emotion,
            "by_tag": summary.by_tag,
            "strategy_adherence_rate": summary.strategy_adherence_rate,
            "by_strategy_adherence": summary.by_strategy_adherence,
            "missing_tag_rate": summary.missing_tag_rate,
            "feeling_rate": summary.feeling_rate,
            "reflection_rate": summary.reflection_rate,
            "result_input_rate": summary.result_input_rate,
        },
        "behavior": {
            "period": period_val,
            "profile": profile,
            "input_rates": input_rates,
            "holding_period_dist": holding_period_dist,
            "position_size_dist": position_size_dist,
            "concentration": concentration,
        },
        "suggestions": {
            "period": period_val,
            "suggestions": suggestions,
        },
    })
