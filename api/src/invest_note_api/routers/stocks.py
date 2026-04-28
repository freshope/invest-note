"""stocks 라우터 — quote + search."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.external.naver_search import StockSearchResult, search_kr
from invest_note_api.external.quotes import fetch_quotes_by_keys

router = APIRouter(prefix="/api/stocks")


@router.get("/quote")
async def get_quotes(
    symbols: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    if not symbols.strip():
        return {}

    keys = [s.strip() for s in symbols.split(",") if s.strip()]
    if not keys:
        return {}

    return await fetch_quotes_by_keys(keys)


@router.get("/search")
async def search_stocks(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[StockSearchResult]:
    q = q.strip()
    if not q or len(q) > 100:
        return []

    return await search_kr(q)
