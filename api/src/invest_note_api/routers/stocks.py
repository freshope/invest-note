"""stocks 라우터 — quote + search."""
from __future__ import annotations

import re

import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, MAX_CODE_LEN, MAX_NAME_LEN
from invest_note_api.external.constants import HTTP_TIMEOUT_SECONDS, NAVER_SEARCH_URL, USER_AGENT
from invest_note_api.external.quotes import fetch_quotes_by_keys

router = APIRouter(prefix="/api/stocks")

_CODE_RE = re.compile(r"^[A-Z0-9]{4,9}$", re.IGNORECASE)

_HEADERS = {"User-Agent": USER_AGENT}


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
) -> list:
    q = q.strip()
    if not q or len(q) > 100:
        return []

    return await _search_kr(q)


async def _search_kr(q: str) -> list:
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                NAVER_SEARCH_URL,
                params={"q": q, "target": "stock"},
                headers=_HEADERS,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        if res.status_code != 200:
            return []

        data = res.json()
        items = data.get("items") or []
        if not isinstance(items, list):
            return []

        results = []
        for item in items[:10]:
            code = item.get("code", "")
            name = item.get("name", "")
            type_code = item.get("typeCode", "")
            if not isinstance(code, str) or not isinstance(name, str):
                continue
            if not _CODE_RE.match(code):
                continue
            results.append({
                "code": code[:MAX_CODE_LEN],
                "name": name[:MAX_NAME_LEN],
                "market": DEFAULT_COUNTRY,
                "exchange": type_code or "",
            })
        return results
    except Exception:
        return []
