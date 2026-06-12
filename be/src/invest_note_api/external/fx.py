"""환율(FX) fetch — Yahoo Finance 1순위 + open.er-api.com 폴백.

USD/KRW 등 통화쌍 현재 환율을 공급자 체인(env FX_PROVIDERS, 기본 `yahoo,er_api`)으로
앞에서부터 시도해 첫 성공값을 사용한다. Yahoo 가 막혀도 무인증 폴백(er_api)으로
해외 평가액의 KRW 환산이 통째로 끊기지 않게 한다. 시세(`quotes.py`)와 동일하게
TTLCache 로 외부 호출 빈도를 낮추고, 캐시 상태(`FxCacheState`)는 `app.state.fx_cache`
에 보관해 라우터에서 주입한다.

환율은 시세보다 변동이 느려 TTL 을 길게(FX_CACHE_TTL) 둔다. 통화쌍이 사실상
USD/KRW 하나뿐이라 stampede 위험이 낮아, 시세의 single-flight 대신 lock 으로
fetch 를 직렬화하는 단순 캐시를 쓴다. 캐시 키는 통화쌍(`base/quote`)만 — 어느 공급자가
채웠든 동일 키를 공유한다(Yahoo 실패→er_api 성공분도 같은 키에 캐시).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

import httpx
from cachetools import TTLCache
from fastapi import Request

from invest_note_api.config import DEFAULT_FX_PROVIDERS
from invest_note_api.domain.trade_types import currency_for_country, trade_country
from invest_note_api.external.constants import (
    CURRENCY_KRW,
    CURRENCY_USD,
    ER_API_LATEST_URL,
    FX_CACHE_MAXSIZE,
    FX_CACHE_TTL,
    QUOTE_ATTEMPT_TIMEOUT,
    USER_AGENT,
    YAHOO_CHART_URL,
)
from invest_note_api.external.provider_registry import resolve_chain

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade

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
        logger.warning("fx 환율 실패(yahoo) %s/%s", base, quote, exc_info=True)
    return None


def _parse_er_api_rate(data: dict, quote: str) -> float:
    """open.er-api.com 응답에서 환율 추출. result!="success" 또는 rates[quote] 결측은 0.0."""
    if data.get("result") != "success":
        return 0.0
    raw = (data.get("rates") or {}).get(quote)
    try:
        return float(raw) if raw else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _fetch_er_api_fx(
    client: httpx.AsyncClient, base: str, quote: str
) -> FxRate | None:
    """open.er-api.com 폴백(무인증). `/v6/latest/{base}` → rates[quote]."""
    try:
        res = await client.get(
            ER_API_LATEST_URL.format(base=base),
            headers=_HEADERS,
            timeout=QUOTE_ATTEMPT_TIMEOUT,
        )
        if res.status_code == 200:
            rate = _parse_er_api_rate(res.json(), quote)
            if rate > 0:
                return {
                    "base": base,
                    "quote": quote,
                    "rate": rate,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
    except Exception:
        logger.warning("fx 환율 실패(er_api) %s/%s", base, quote, exc_info=True)
    return None


# 환율 공급자 registry — env FX_PROVIDERS 의 이름이 여기 등록돼 있어야 한다.
_FX_REGISTRY: dict[str, Callable] = {
    "yahoo": _fetch_yahoo_fx,
    "er_api": _fetch_er_api_fx,
}


def validate_fx_providers(providers: Sequence[str]) -> None:
    """env FX_PROVIDERS 오타를 앱 startup 에서 fail-fast.

    요청 경로(get_fx_rate)는 lock 안에서 resolve_chain 을 호출하므로, 빈 체인/오타를
    부팅 시점에 거부해 사용자 대면 실패를 막는다. 빈 체인도 거부(quotes 와 동일 사상).
    """
    if not providers:
        raise ValueError("fx: 공급자 체인이 비어 있습니다 (FX_PROVIDERS 확인)")
    resolve_chain(providers, _FX_REGISTRY, domain="fx")


async def get_fx_rate(
    state: FxCacheState,
    *,
    client: httpx.AsyncClient,
    base: str = CURRENCY_USD,
    quote: str = CURRENCY_KRW,
    force_refresh: bool = False,
    providers: Sequence[str] = DEFAULT_FX_PROVIDERS,
) -> FxRate | None:
    """통화쌍 환율 조회(캐시 경유, 공급자 체인 fallback). 실패 시 None.

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 공유 인스턴스.
    `providers` 는 호출측(라우터)이 settings.fx_provider_list 를 전달 — 내부에서
    get_settings() 를 읽지 않는다(테스트 격리·암묵 의존 방지).
    캐시 hit 은 lock 없이 즉시 반환(fast-path) — lock 이 공급자 체인 전체(최대
    len(providers)×QUOTE_ATTEMPT_TIMEOUT)를 감싸므로, 한 호출자가 fetch 중일 때 순수 캐시
    읽기까지 직렬화되는 것을 막는다. 통화쌍이 사실상 USD/KRW 하나라 contention 은 낮다.
    단일 이벤트루프라 await 없는 TTLCache 접근은 안전. miss/refresh 만 lock 으로 직렬화해
    stampede 를 막는다(진입 후 재확인 — 대기 중 다른 호출자가 채웠으면 fetch 생략).
    """
    key = f"{base}/{quote}"
    if not force_refresh:
        cached = state.cache.get(key)
        if cached is not None:
            return cached
    async with state.lock:
        cached = state.cache.get(key)
        if not force_refresh and cached is not None:
            return cached
        # 공급자 체인을 앞에서부터 시도 — 첫 성공값을 캐시·반환.
        for fetch in resolve_chain(providers, _FX_REGISTRY, domain="fx"):
            result = await fetch(client, base, quote)
            if result is not None:
                state.cache[key] = result
                return result
        # 전체 체인 실패: None 을 장기 TTL(FX_CACHE_TTL) 캐시에 박지 않는다 — 일시 실패 1회가
        # 전 해외 보유 평가액을 10분간 가리는 것을 막고 다음 요청에서 재시도한다. 직전 성공값이
        # 있으면 stale 로 유지(환율은 느리게 변해 허용 가능), 없으면 None.
        return cached


async def fetch_usdkrw(
    state: FxCacheState,
    client: httpx.AsyncClient,
    *,
    force_refresh: bool = False,
    providers: Sequence[str] = DEFAULT_FX_PROVIDERS,
) -> float | None:
    """USD/KRW 환율 숫자만 반환(못 받으면 None) — 라우터 집계의 KRW 환산용 단축."""
    fx = await get_fx_rate(
        state, client=client, force_refresh=force_refresh, providers=providers
    )
    return fx["rate"] if fx else None


async def usdkrw_if_foreign(
    trades: Iterable["Trade"],
    state: FxCacheState,
    client: httpx.AsyncClient,
    *,
    force_refresh: bool = False,
    providers: Sequence[str] = DEFAULT_FX_PROVIDERS,
) -> float | None:
    """비-KRW(해외) 거래가 하나라도 있으면 USD/KRW 환율을 fetch, 없으면 None.

    portfolio/analysis 라우터에 중복되던 "해외 보유 게이트 + fetch_usdkrw" 묶음을 캡슐화한다.
    호출 위치/동시성 구조(lite 분기·create_task)는 각 라우터가 유지한다.
    """
    if not any(currency_for_country(trade_country(t)) != CURRENCY_KRW for t in trades):
        return None
    return await fetch_usdkrw(state, client, force_refresh=force_refresh, providers=providers)
