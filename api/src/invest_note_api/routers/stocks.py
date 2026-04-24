"""stocks 라우터 — quote + search."""
from __future__ import annotations

import re

import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.domain.trade_types import COUNTRY_US
from invest_note_api.external.constants import HTTP_TIMEOUT_SECONDS, NAVER_SEARCH_URL, USER_AGENT, YAHOO_SEARCH_URL
from invest_note_api.external.quotes import fetch_quotes_by_keys

router = APIRouter(prefix="/api/stocks")

_HAS_KOREAN = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")
_IS_KR_CODE = re.compile(r"^\d{6}$")
_CODE_RE = re.compile(r"^[A-Z0-9]{4,9}$", re.IGNORECASE)

_HEADERS = {"User-Agent": USER_AGENT}
_EXCHANGE_MAP = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
    "NYQ": "NYSE", "NYS": "NYSE",
    "PCX": "NYSE ARCA",
    "ASE": "AMEX",
    "BTS": "CBOE",
}


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

    if _HAS_KOREAN.search(q) or _IS_KR_CODE.match(q):
        return await _search_kr(q)
    return await _search_us(q)


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
                "code": code[:20],
                "name": name[:50],
                "market": "KR",
                "exchange": type_code or "",
            })
        return results
    except Exception:
        return []


async def _search_us(q: str) -> list:
    try:
        params = {
            "q": q,
            "quotesCount": "10",
            "newsCount": "0",
            "listsCount": "0",
        }
        async with httpx.AsyncClient() as client:
            res = await client.get(
                YAHOO_SEARCH_URL,
                params=params,
                headers=_HEADERS,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        if res.status_code != 200:
            return []

        data = res.json()
        quotes = data.get("quotes") or []
        if not isinstance(quotes, list):
            return []

        results = []
        for item in quotes[:10]:
            if item.get("quoteType") not in ("EQUITY", "ETF"):
                continue
            exchange = item.get("exchange", "")
            if exchange not in _EXCHANGE_MAP:
                continue
            symbol = item.get("symbol", "")
            name = (item.get("shortname") or item.get("longname") or symbol)[:50]
            results.append({
                "code": symbol,
                "name": name,
                "market": COUNTRY_US,
                "exchange": _EXCHANGE_MAP.get(exchange, exchange),
            })
        return results
    except Exception:
        return []
