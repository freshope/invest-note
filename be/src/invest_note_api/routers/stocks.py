"""stocks 라우터 — quote + search."""
from __future__ import annotations

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import stocks_repo
from invest_note_api.db_ops.stocks_repo import StockSearchResult
from invest_note_api.external.constants import CURRENCY_KRW, CURRENCY_USD
from invest_note_api.external.fx import (
    FxCacheState,
    FxRate,
    get_fx_cache_state,
    get_fx_rate,
)
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.naver_search import search_kr
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)

router = APIRouter(prefix="/stocks")


@router.get("/quote")
async def get_quotes(
    symbols: str = Query(default=""),
    refresh: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not symbols.strip():
        return {}

    keys = [s.strip() for s in symbols.split(",") if s.strip()]
    if not keys:
        return {}

    return await fetch_quotes_by_keys(
        quote_state,
        keys,
        client=http_client,
        force_refresh=refresh,
        providers=settings.quote_provider_list,
        us_providers=settings.us_quote_provider_list,
    )


_FX_ALLOWED = {CURRENCY_KRW, CURRENCY_USD}


@router.get("/fx")
async def get_fx(
    base: str = Query(default=CURRENCY_USD),
    quote: str = Query(default=CURRENCY_KRW),
    refresh: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    fx_state: FxCacheState = Depends(get_fx_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
) -> FxRate | None:
    """통화쌍 현재 환율. 실패 시 null. MVP 는 USD/KRW 만 허용."""
    base, quote = base.upper(), quote.upper()
    if base not in _FX_ALLOWED or quote not in _FX_ALLOWED or base == quote:
        raise HTTPException(status_code=400, detail="지원하지 않는 통화쌍입니다.")
    return await get_fx_rate(
        fx_state,
        client=http_client,
        base=base,
        quote=quote,
        force_refresh=refresh,
        providers=settings.fx_provider_list,
    )


@router.get("/meta")
async def get_stock_meta(
    codes: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """종목 코드 목록(콤마 구분, KR 6자리) → {code: 메타}. 뱃지용 배치 조회."""
    parsed = list(dict.fromkeys(c.strip() for c in codes.split(",") if c.strip()))
    if not parsed:
        return {}
    parsed = parsed[:200]

    # stocks 는 public read-only 마스터 — RLS 미적용이라 plain connection 으로 조회.
    async with pool.acquire() as conn:
        return await stocks_repo.fetch_meta(conn, parsed)


@router.get("/search")
async def search_stocks(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> list[StockSearchResult]:
    q = q.strip()
    if not q or len(q) > 100:
        return []

    if settings.stock_search_provider == "db":
        # stocks 는 public read-only 마스터 — RLS 미적용이라 plain connection 으로 조회.
        # KR + US 를 함께 검색(결과의 market 필드로 국가 구분). FE 필터가 표시 국가를 정한다.
        async with pool.acquire() as conn:
            return await stocks_repo.search_multi(conn, q)

    # 기본: Naver 자동완성(data.go.kr 모니터링 기간 동안 이전 방식 사용).
    return await search_kr(q, client=http_client)
