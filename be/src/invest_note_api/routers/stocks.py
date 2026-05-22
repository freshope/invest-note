"""stocks 라우터 — quote + search."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.naver_search import StockSearchResult, search_kr
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)

router = APIRouter(prefix="/stocks")


@router.get("/quote")
async def get_quotes(
    symbols: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> dict:
    if not symbols.strip():
        return {}

    keys = [s.strip() for s in symbols.split(",") if s.strip()]
    if not keys:
        return {}

    return await fetch_quotes_by_keys(quote_state, keys, client=http_client)


@router.get("/search")
async def search_stocks(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> list[StockSearchResult]:
    q = q.strip()
    if not q or len(q) > 100:
        return []

    return await search_kr(q, client=http_client)
