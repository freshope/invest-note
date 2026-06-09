"""환율(FX) fetch — Yahoo Finance.

USD/KRW 등 통화쌍 현재 환율을 Yahoo chart v8(`{symbol}=X`)에서 조회한다.
시세(`quotes.py`)와 동일하게 TTLCache 로 외부 호출 빈도를 낮추고, 캐시 상태
(`FxCacheState`)는 `app.state.fx_cache` 에 보관해 라우터에서 주입한다.

환율은 시세보다 변동이 느려 TTL 을 길게(FX_CACHE_TTL) 둔다. 통화쌍이 사실상
USD/KRW 하나뿐이라 stampede 위험이 낮아, 시세의 single-flight 대신 lock 으로
fetch 를 직렬화하는 단순 캐시를 쓴다.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache
from fastapi import Request

from invest_note_api.external.constants import (
    CURRENCY_KRW,
    CURRENCY_USD,
    FX_CACHE_MAXSIZE,
    FX_CACHE_TTL,
    QUOTE_ATTEMPT_TIMEOUT,
    USER_AGENT,
    YAHOO_CHART_URL,
)

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}


class FxRate(TypedDict):
    base: str
    quote: str
    rate: float  # base 1단위 = rate * quote (예: USD/KRW 1350.0 → 1 USD = 1350 KRW)
    as_of: str


@dataclass
class FxCacheState:
    cache: TTLCache[str, dict | None] = field(
        default_factory=lambda: TTLCache(maxsize=FX_CACHE_MAXSIZE, ttl=FX_CACHE_TTL)
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def get_fx_cache_state(request: Request) -> FxCacheState:
    return request.app.state.fx_cache


def _yahoo_fx_symbol(base: str, quote: str) -> str:
    """Yahoo FX 심볼. USD base 는 `{quote}=X`(예: KRW=X=USDKRW), 그 외는 `{base}{quote}=X`."""
    if base == CURRENCY_USD:
        return f"{quote}=X"
    return f"{base}{quote}=X"


def _parse_yahoo_fx_rate(data: dict) -> float:
    """Yahoo chart v8 응답에서 환율(meta.regularMarketPrice) 추출. 없으면 0.0."""
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return 0.0
    raw = (result[0].get("meta") or {}).get("regularMarketPrice")
    try:
        return float(raw) if raw else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _fetch_yahoo_fx(
    client: httpx.AsyncClient, base: str, quote: str
) -> FxRate | None:
    symbol = _yahoo_fx_symbol(base, quote)
    try:
        res = await client.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            headers=_HEADERS,
            timeout=QUOTE_ATTEMPT_TIMEOUT,
        )
        if res.status_code == 200:
            rate = _parse_yahoo_fx_rate(res.json())
            if rate > 0:
                return {
                    "base": base,
                    "quote": quote,
                    "rate": rate,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
    except Exception:
        logger.warning("fx 환율 실패 %s/%s", base, quote, exc_info=True)
    return None


async def get_fx_rate(
    state: FxCacheState,
    *,
    client: httpx.AsyncClient,
    base: str = CURRENCY_USD,
    quote: str = CURRENCY_KRW,
    force_refresh: bool = False,
) -> FxRate | None:
    """통화쌍 환율 조회(캐시 경유). 실패 시 None.

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 공유 인스턴스.
    lock 으로 fetch 를 직렬화 — 통화쌍이 적어 직렬화 비용이 무시할 만하고 stampede 를 막는다.
    """
    key = f"{base}/{quote}"
    async with state.lock:
        cached = state.cache.get(key)
        if not force_refresh and cached is not None:
            return cached
        result = await _fetch_yahoo_fx(client, base, quote)
        if result is not None:
            state.cache[key] = result
            return result
        # fetch 실패: None 을 장기 TTL(FX_CACHE_TTL) 캐시에 박지 않는다 — 일시 실패 1회가
        # 전 해외 보유 평가액을 10분간 가리는 것을 막고 다음 요청에서 재시도한다. 직전 성공값이
        # 있으면 stale 로 유지(환율은 느리게 변해 허용 가능), 없으면 None.
        return cached


async def fetch_usdkrw(
    state: FxCacheState, client: httpx.AsyncClient, *, force_refresh: bool = False
) -> float | None:
    """USD/KRW 환율 숫자만 반환(못 받으면 None) — 라우터 집계의 KRW 환산용 단축."""
    fx = await get_fx_rate(state, client=client, force_refresh=force_refresh)
    return fx["rate"] if fx else None
