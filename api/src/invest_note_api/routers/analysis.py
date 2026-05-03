"""analysis 라우터 — dashboard 단일 엔드포인트."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict

import asyncpg
import httpx
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
from invest_note_api.domain.trade_types import TRADE_TYPE_BUY
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)
from invest_note_api.schemas.analysis_response import AnalysisDashboardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis")

# 보유 기간 구간 — 임계값은 inclusive (`days <= threshold`)
_HOLDING_BUCKETS: list[tuple[float, str]] = [
    (1, "1일 이내"),
    (7, "1주 이내"),
    (30, "1개월 이내"),
    (90, "3개월 이내"),
    (180, "6개월 이내"),
    (365, "1년 이내"),
    (float("inf"), "1년 이상"),
]
# 매수 금액 구간 — 임계값은 strict less-than (`amount < threshold`)
_SIZE_BUCKETS: list[tuple[float, str]] = [
    (500_000, "50만 미만"),
    (1_000_000, "50~100만"),
    (5_000_000, "100~500만"),
    (10_000_000, "500만~1천만"),
    (50_000_000, "1천~5천만"),
    (float("inf"), "5천만 이상"),
]
_HOLDING_ORDER = [label for _, label in _HOLDING_BUCKETS]
_SIZE_ORDER = [label for _, label in _SIZE_BUCKETS]


def _first_bucket_label(
    value: float, buckets: list[tuple[float, str]], *, inclusive: bool
) -> str:
    for threshold, label in buckets:
        if (value <= threshold) if inclusive else (value < threshold):
            return label
    return buckets[-1][1]


def _holding_bucket(days: int) -> str:
    return _first_bucket_label(days, _HOLDING_BUCKETS, inclusive=True)


def _size_bucket(amount: float) -> str:
    return _first_bucket_label(amount, _SIZE_BUCKETS, inclusive=False)


@router.get(
    "/dashboard",
    response_model=AnalysisDashboardResponse,
    response_model_exclude_none=True,
)
async def get_analysis_dashboard(
    period: str = Query(default=DEFAULT_PERIOD),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> AnalysisDashboardResponse:
    async with acquire_for_user(pool, user.id) as conn:
        all_trades = await list_trades(conn, user.id)
    period_val = parse_period(period)
    trades = filter_by_period(all_trades, period_val)

    pnl_map = build_pnl_map(trades)
    holding_days_map = compute_holding_days_map(trades)
    positions0, _ = build_positions(all_trades)

    positions = positions0
    try:
        quotes = await fetch_quotes_by_keys(
            quote_state, [p.key for p in positions0], client=http_client
        )
        positions = merge_quotes(positions0, quotes)
    except Exception as e:
        logger.warning("시세 fetch 실패, cost_basis fallback: %s", e)

    concentration = compute_concentration(positions, all_trades)
    summary = compute_summary(trades, pnl_map, holding_days_map)
    # all_trades 입력 — compute_profile 의 누적 일관성 평가용 (compute_summary 내부 호출과는 의도가 다름)
    strategy_evals = build_strategy_evaluations(all_trades, holding_days_map)
    profile, input_rates = compute_profile(trades, holding_days_map, strategy_evals)
    suggestions = evaluate_rules(
        {"summary": summary, "profile": profile, "concentration": concentration}
    )

    holding_dist = Counter(_holding_bucket(d) for d in holding_days_map.values())
    holding_period_dist = [
        {"bucket": b, "count": holding_dist[b]}
        for b in _HOLDING_ORDER
        if b in holding_dist
    ]

    size_dist = Counter(
        _size_bucket(t.total_amount) for t in trades if t.trade_type == TRADE_TYPE_BUY
    )
    position_size_dist = [
        {"bucket": b, "count": size_dist[b]}
        for b in _SIZE_ORDER
        if b in size_dist
    ]

    return AnalysisDashboardResponse.model_validate({
        "period": period_val,
        "summary": {"period": period_val, **asdict(summary)},
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
