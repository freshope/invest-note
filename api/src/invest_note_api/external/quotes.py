"""시세 fetch — Naver Finance (KR) + Yahoo Finance v8 (US).

캐싱: TTLCache(maxsize=512, ttl=60) + asyncio.Lock으로 symbol:country 키별 60초 in-memory 캐시.
Next.js `fetch(..., { next: { revalidate: 60 } })` 동작과 등가.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache

from invest_note_api.external.constants import (
    HTTP_TIMEOUT_SECONDS,
    NAVER_BASIC_URL,
    NAVER_REALTIME_URL,
    QUOTE_CACHE_MAXSIZE,
    QUOTE_CACHE_TTL,
    USER_AGENT,
    YAHOO_CHART_URL,
)

_HEADERS = {"User-Agent": USER_AGENT}

_cache: TTLCache[str, dict | None] = TTLCache(maxsize=QUOTE_CACHE_MAXSIZE, ttl=QUOTE_CACHE_TTL)
_cache_lock = asyncio.Lock()


class QuoteResult(TypedDict):
    price: float
    currency: str
    as_of: str


async def _fetch_kr_price(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    try:
        url = NAVER_REALTIME_URL.format(code=code)
        res = await client.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if res.status_code == 200:
            data = res.json()
            item = (data.get("datas") or [{}])[0] if data.get("datas") else data.get("data") or data
            raw = item.get("closePriceRaw") or item.get("now") or (
                str(item.get("closePrice", "")).replace(",", "") if item.get("closePrice") else None
            )
            price = float(raw) if raw else 0.0
            if price > 0:
                return {"price": price, "currency": "KRW", "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception:
        pass

    # 백업: stock basic API
    try:
        url = NAVER_BASIC_URL.format(code=code)
        res = await client.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if res.status_code == 200:
            data = res.json()
            raw = (
                data.get("closePriceRaw")
                or str(data.get("stockEndPrice", "")).replace(",", "")
                or str(data.get("closePrice", "")).replace(",", "")
            )
            price = float(raw) if raw else 0.0
            if price > 0:
                return {"price": price, "currency": "KRW", "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception:
        pass

    return None


async def _fetch_us_price(client: httpx.AsyncClient, symbol: str) -> QuoteResult | None:
    try:
        url = YAHOO_CHART_URL.format(symbol=symbol)
        res = await client.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if res.status_code != 200:
            return None
        data = res.json()
        results = data.get("chart", {}).get("result") or []
        if not results:
            return None
        meta = results[0].get("meta", {})
        price = float(meta.get("regularMarketPrice") or 0)
        if price > 0:
            return {
                "price": price,
                "currency": meta.get("currency", "USD"),
                "as_of": datetime.now(timezone.utc).isoformat(),
            }
    except Exception:
        pass
    return None


async def _get_cached(key: str, fetch_fn) -> dict | None:
    async with _cache_lock:
        if key in _cache:
            return _cache[key]

    result = await fetch_fn()

    async with _cache_lock:
        _cache[key] = result

    return result


async def fetch_quotes_by_keys(keys: list[str]) -> dict[str, QuoteResult | None]:
    """keys 형식: "종목코드:국가" (예: "005930:KR", "AAPL:US")"""
    if not keys:
        return {}

    entries = []
    for key in keys:
        parts = key.split(":")
        code = parts[0][:20] if parts else ""
        country = parts[1] if len(parts) > 1 else "KR"
        if code:
            entries.append({"code": code, "country": country, "key": key})

    async def _null() -> None:
        return None

    async with httpx.AsyncClient() as client:
        tasks = []
        for e in entries:
            if e["country"] == "KR":
                cache_key = f"KR:{e['code']}"
                tasks.append(_get_cached(cache_key, lambda c=client, code=e["code"]: _fetch_kr_price(c, code)))
            elif e["country"] == "US":
                cache_key = f"US:{e['code']}"
                tasks.append(_get_cached(cache_key, lambda c=client, sym=e["code"]: _fetch_us_price(c, sym)))
            else:
                tasks.append(_null())

        results = await asyncio.gather(*tasks, return_exceptions=True)

    out: dict[str, QuoteResult | None] = {}
    for e, result in zip(entries, results):
        if isinstance(result, Exception):
            out[e["key"]] = None
        else:
            out[e["key"]] = result

    return out
