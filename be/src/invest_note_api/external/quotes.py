"""시세 fetch — Naver Finance (KR).

캐싱: TTLCache(maxsize=512, ttl=10) + asyncio.Lock으로 symbol:country 키별 10초 in-memory 캐시.
pull-to-refresh 직후 새 시세를 받을 수 있도록 짧게 설정.

캐시 상태(`QuoteCacheState`)는 `app.state.quote_cache` 에 보관하고 라우터에서
`Depends(get_quote_cache_state)` 로 주입한다.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache
from fastapi import Request

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
    YAHOO_CHART_URL,
)
from invest_note_api.utils.numbers import strip_comma_number

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}


@dataclass
class QuoteCacheState:
    cache: TTLCache[str, dict | None] = field(
        default_factory=lambda: TTLCache(maxsize=QUOTE_CACHE_MAXSIZE, ttl=QUOTE_CACHE_TTL)
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    inflight: dict[str, asyncio.Future] = field(default_factory=dict)


def get_quote_cache_state(request: Request) -> QuoteCacheState:
    return request.app.state.quote_cache


class QuoteResult(TypedDict):
    price: float
    currency: str
    as_of: str


def _parse_realtime_price(data: dict) -> float:
    item = (data.get("datas") or [{}])[0] if data.get("datas") else data.get("data") or data
    raw = (
        item.get("closePriceRaw")
        or item.get("now")
        or strip_comma_number(item.get("closePrice"))
    )
    return float(raw) if raw else 0.0


def _parse_basic_price(data: dict) -> float:
    raw = (
        data.get("closePriceRaw")
        or strip_comma_number(data.get("stockEndPrice"))
        or strip_comma_number(data.get("closePrice"))
    )
    return float(raw) if raw else 0.0


def _parse_yahoo_chart_price(data: dict) -> float:
    """Yahoo chart v8: chart.result[0].meta.regularMarketPrice."""
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return 0.0
    meta = result[0].get("meta") or {}
    raw = meta.get("regularMarketPrice")
    return float(raw) if raw else 0.0


async def _try_endpoint(
    client: httpx.AsyncClient,
    url: str,
    parse_price: Callable[[dict], float],
    log_label: str,
    code: str,
) -> QuoteResult | None:
    try:
        res = await client.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if res.status_code == 200:
            price = parse_price(res.json())
            if price > 0:
                return {
                    "price": price,
                    "currency": CURRENCY_KRW,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
    except Exception:
        logger.warning("%s 시세 실패 code=%s", log_label, code, exc_info=True)
    return None


async def _fetch_kr_price(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    result = await _try_endpoint(
        client,
        NAVER_REALTIME_URL.format(code=code),
        _parse_realtime_price,
        "naver realtime",
        code,
    )
    if result is not None:
        return result
    result = await _try_endpoint(
        client,
        NAVER_BASIC_URL.format(code=code),
        _parse_basic_price,
        "naver basic",
        code,
    )
    if result is not None:
        return result
    # Naver 차단/장애 fallback — KOSPI(.KS) → KOSDAQ(.KQ) 순으로 Yahoo 시도.
    # market 정보가 없어 두 suffix 모두 확인. 둘 다 200을 주더라도 잘못된 시장은
    # result.length=0 이라 _parse_yahoo_chart_price 가 0.0 을 반환하여 자동 스킵.
    for suffix in (".KS", ".KQ"):
        result = await _try_endpoint(
            client,
            YAHOO_CHART_URL.format(symbol=f"{code}{suffix}"),
            _parse_yahoo_chart_price,
            f"yahoo {suffix[1:]}",
            code,
        )
        if result is not None:
            return result
    return None


async def _get_cached(state: QuoteCacheState, key: str, fetch_fn) -> dict | None:
    """동일 키 동시 요청은 single-flight — 첫 호출자만 fetch_fn 실행."""
    async with state.lock:
        if key in state.cache:
            return state.cache[key]
        existing = state.inflight.get(key)
        if existing is not None:
            future, owner = existing, False
        else:
            future = asyncio.get_running_loop().create_future()
            state.inflight[key] = future
            owner = True

    if not owner:
        return await future

    try:
        result = await fetch_fn()
    except Exception as exc:
        async with state.lock:
            state.inflight.pop(key, None)
        if not future.done():
            future.set_exception(exc)
        raise

    async with state.lock:
        state.cache[key] = result
        state.inflight.pop(key, None)
    if not future.done():
        future.set_result(result)
    return result


async def fetch_quotes_by_keys(
    state: QuoteCacheState,
    keys: list[str],
    *,
    client: httpx.AsyncClient,
) -> dict[str, QuoteResult | None]:
    """keys 형식: "종목코드:국가" (예: "005930:KR"). KR 외 국가는 MVP에서 null.

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 lifespan-managed 공유 인스턴스.
    """
    if not keys:
        return {}

    entries = []
    for key in keys:
        parts = key.split(":")
        code = parts[0][:MAX_CODE_LEN] if parts else ""
        country = parts[1] if len(parts) > 1 else DEFAULT_COUNTRY
        if code:
            entries.append({"code": code, "country": country, "key": key})

    kr_entries = [e for e in entries if e["country"] == DEFAULT_COUNTRY]
    tasks = [
        _get_cached(
            state,
            position_key(e["code"], DEFAULT_COUNTRY),
            lambda code=e["code"]: _fetch_kr_price(client, code),
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
