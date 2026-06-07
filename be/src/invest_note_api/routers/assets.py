"""assets 라우터 — 자산 변화(일별 평가액 추이). 계좌뷰/종목뷰 단일 엔드포인트.

흐름: 거래 로드 → (커넥션 밖에서) data.go.kr 종가 backfill → get_closes → 오늘 라이브 시세
→ asset_history 순수 계산 → 응답. data.go.kr fetch 는 느리므로(14~18초) 풀 커넥션을
잡고 있지 않도록 fetch 전후로 커넥션 획득을 분리한다(portfolio/admin 과 동일 정책).
"""
from __future__ import annotations

import logging
from datetime import datetime

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops import daily_prices_repo
from invest_note_api.db_ops.trades_repo import list_trades_with_account
from invest_note_api.domain.asset_history import (
    compute_asset_history,
    market_open_today,
    scope_earliest_date,
    scope_tickers,
)
from invest_note_api.domain.portfolio import holding_invested_amount
from invest_note_api.domain.trade_utils import KST, position_key
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)
from invest_note_api.services import daily_price_seed
from invest_note_api.schemas.asset_response import AssetHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets")


@router.get("/history", response_model=AssetHistoryResponse)
async def get_asset_history(
    account_id: str | None = Query(default=None, alias="accountId"),
    ticker: str | None = Query(default=None),
    country: str = Query(default="KR"),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    settings: Settings = Depends(get_settings),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> AssetHistoryResponse:
    is_stock_view = bool(ticker)
    today = datetime.now(KST).date()

    # 1) 스코프 거래 로드(accountId/ticker/country push). 계좌뷰/종목뷰 모두 country 필터 —
    # 종가 적재(data.go.kr)·시세 조회가 country 단위라, 다른 국가 보유분이 섞이면
    # 값에서 조용히 빠지면서 incomplete 만 세우게 된다. 스코프를 country 로 일관시킨다.
    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(
            conn,
            user.id,
            account_id=account_id,
            ticker=ticker if is_stock_view else None,
            country=country,
        )

    if not trades:
        return AssetHistoryResponse.model_validate(
            {"series": [], "items": [], "incomplete": False, "as_of": _now_iso()}
        )

    earliest = scope_earliest_date(trades, today)
    tickers = scope_tickers(trades)

    # 현재 보유분 매수 원금 — 차트의 손익 기준 가이드 라인 값.
    # 보유가 없으면 None(FE 는 기존 단색 차트 폴백).
    invested_amount = holding_invested_amount(trades)

    # 2) backfill(커넥션 보유 — fetch 가 느리지만 콜드스타트는 spec 수용. watermark 증분.)
    incomplete_fetch = False
    async with acquire_for_user(pool, user.id) as conn:
        if tickers:
            incomplete_fetch = await daily_price_seed.backfill_closes(
                conn,
                settings.data_go_kr_api_key,
                tickers,
                earliest,
                today,
                country_code=country,
                primary_provider=settings.daily_price_provider,
                gap_provider=settings.daily_price_gap_provider,
            )
        closes = await daily_prices_repo.get_closes(
            conn, tickers, earliest, today, country_code=country
        )

    # 3) 오늘 점 라이브 시세 — ticker → price 맵.
    live_quotes: dict[str, float] = {}
    quotes: dict = {}
    if tickers:
        keys = [position_key(tk, country) for tk in tickers]
        try:
            quotes = await fetch_quotes_by_keys(
                quote_state, keys, client=http_client, providers=settings.quote_provider_list
            )
        except Exception:
            logger.warning("asset_history 시세 조회 실패 user_id=%s", user.id, exc_info=True)
            quotes = {}
        for tk in tickers:
            q = quotes.get(position_key(tk, country))
            if q is not None:
                live_quotes[tk] = q["price"]

    # 4) 순수 계산 — 휴장일(시세 traded_on ≠ 오늘)이면 오늘 점 제외.
    result = compute_asset_history(
        trades,
        closes,
        live_quotes,
        today=today,
        is_stock_view=is_stock_view,
        include_today=market_open_today(list(quotes.values()), today),
    )

    return AssetHistoryResponse.model_validate(
        {
            "series": result.series,
            "items": result.items,
            "incomplete": result.incomplete or incomplete_fetch,
            "as_of": _now_iso(),
            "invested_amount": invested_amount,
        }
    )


def _now_iso() -> str:
    """마지막 점 기준시각 — KST ISO8601(+09:00). 오늘 점은 라이브 시세 시각."""
    return datetime.now(KST).isoformat()
