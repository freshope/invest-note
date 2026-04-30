"""시세 fetch — Naver Finance (KR).

캐싱: TTLCache(maxsize=512, ttl=60) + asyncio.Lock으로 symbol:country 키별 60초 in-memory 캐시.
Next.js `fetch(..., { next: { revalidate: 60 } })` 동작과 등가.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache

from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, MAX_CODE_LEN
from invest_note_api.domain.trade_utils import position_key
from invest_note_api.external.constants import (
    CURRENCY_KRW,
    HTTP_TIMEOUT_SECONDS,
    NAVER_BASIC_URL,
    NAVER_REALTIME_URL,
    QUOTE_CACHE_MAXSIZE,
    QUOTE_CACHE_TTL,
    USER_AGENT,
)
from invest_note_api.utils.numbers import strip_comma_number

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}

_cache: TTLCache[str, dict | None] = TTLCache(maxsize=QUOTE_CACHE_MAXSIZE, ttl=QUOTE_CACHE_TTL)
_cache_lock = asyncio.Lock()
_inflight: dict[str, asyncio.Future] = {}


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
            raw = (
                item.get("closePriceRaw")
                or item.get("now")
                or strip_comma_number(item.get("closePrice"))
            )
            price = float(raw) if raw else 0.0
            if price > 0:
                return {"price": price, "currency": CURRENCY_KRW, "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception:
        logger.warning("naver realtime 시세 실패 code=%s", code, exc_info=True)

    # 백업: stock basic API
    try:
        url = NAVER_BASIC_URL.format(code=code)
        res = await client.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if res.status_code == 200:
            data = res.json()
            raw = (
                data.get("closePriceRaw")
                or strip_comma_number(data.get("stockEndPrice"))
                or strip_comma_number(data.get("closePrice"))
            )
            price = float(raw) if raw else 0.0
            if price > 0:
                return {"price": price, "currency": CURRENCY_KRW, "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception:
        logger.warning("naver basic 시세 실패 code=%s", code, exc_info=True)

    return None


async def _get_cached(key: str, fetch_fn) -> dict | None:
    """동일 키 동시 요청은 single-flight — 첫 호출자만 fetch_fn 실행."""
    async with _cache_lock:
        if key in _cache:
            return _cache[key]
        existing = _inflight.get(key)
        if existing is not None:
            future, owner = existing, False
        else:
            future = asyncio.get_running_loop().create_future()
            _inflight[key] = future
            owner = True

    if not owner:
        return await future

    try:
        result = await fetch_fn()
    except Exception as exc:
        async with _cache_lock:
            _inflight.pop(key, None)
        if not future.done():
            future.set_exception(exc)
        raise

    async with _cache_lock:
        _cache[key] = result
        _inflight.pop(key, None)
    if not future.done():
        future.set_result(result)
    return result


async def fetch_quotes_by_keys(keys: list[str]) -> dict[str, QuoteResult | None]:
    """keys 형식: "종목코드:국가" (예: "005930:KR"). KR 외 국가는 MVP에서 null."""
    if not keys:
        return {}

    entries = []
    for key in keys:
        parts = key.split(":")
        code = parts[0][:MAX_CODE_LEN] if parts else ""
        country = parts[1] if len(parts) > 1 else DEFAULT_COUNTRY
        if code:
            entries.append({"code": code, "country": country, "key": key})

    async with httpx.AsyncClient() as client:
        kr_entries = [e for e in entries if e["country"] == DEFAULT_COUNTRY]
        tasks = [
            _get_cached(
                position_key(e["code"], DEFAULT_COUNTRY),
                lambda c=client, code=e["code"]: _fetch_kr_price(c, code),
            )
            for e in kr_entries
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

    out: dict[str, QuoteResult | None] = {e["key"]: None for e in entries}
    for e, result in zip(kr_entries, results):
        if isinstance(result, Exception):
            out[e["key"]] = None
        else:
            out[e["key"]] = result

    return out
