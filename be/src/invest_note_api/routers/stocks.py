"""stocks 라우터 — quote + search."""
from __future__ import annotations

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import stocks_repo
from invest_note_api.db_ops.stocks_repo import StockSearchResult
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
) -> dict:
    if not symbols.strip():
        return {}

    keys = [s.strip() for s in symbols.split(",") if s.strip()]
    if not keys:
        return {}

    return await fetch_quotes_by_keys(quote_state, keys, client=http_client, force_refresh=refresh)


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
        async with pool.acquire() as conn:
            return await stocks_repo.search(conn, q)

    # 기본: Naver 자동완성(data.go.kr 모니터링 기간 동안 이전 방식 사용).
    return await search_kr(q, client=http_client)
