"""시세 fetch — Naver Finance (KR).

캐싱: TTLCache(maxsize, ttl) + asyncio.Lock으로 symbol:country 키별 in-memory 캐시.
baseline TTL 은 길게 두고, pull-to-refresh 는 `force_refresh=True`(라우터의 `refresh=1`)로
캐시를 우회해 새 시세를 받는다.

캐시 상태(`QuoteCacheState`)는 `app.state.quote_cache` 에 보관하고 라우터에서
`Depends(get_quote_cache_state)` 로 주입한다.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache
from fastapi import Request

from invest_note_api.config import DEFAULT_QUOTE_PROVIDERS
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, MAX_CODE_LEN
from invest_note_api.domain.trade_utils import KST, position_key
from invest_note_api.external.constants import (
    CURRENCY_KRW,
    NAVER_BASIC_URL,
    NAVER_REALTIME_URL,
    QUOTE_ATTEMPT_TIMEOUT,
    QUOTE_CACHE_MAXSIZE,
    QUOTE_CACHE_TTL,
    QUOTE_FETCH_DEADLINE,
    USER_AGENT,
    YAHOO_CHART_URL,
)
from invest_note_api.external.provider_registry import resolve_chain
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
    traded_on: str | None  # 마지막 체결 KST 날짜(ISO). 휴장일 판정용 — 소스에 없으면 None.


def _parse_realtime_price(data: dict) -> tuple[float, str | None]:
    item = (data.get("datas") or [{}])[0] if data.get("datas") else data.get("data") or data
    raw = (
        item.get("closePriceRaw")
        or item.get("now")
        or strip_comma_number(item.get("closePrice"))
    )
    # localTradedAt: "2026-06-05T15:30:00+09:00" — 앞 10자가 KST 날짜.
    traded_at = item.get("localTradedAt")
    traded_on = traded_at[:10] if isinstance(traded_at, str) and len(traded_at) >= 10 else None
    return (float(raw) if raw else 0.0, traded_on)


def _parse_basic_price(data: dict) -> tuple[float, str | None]:
    raw = (
        data.get("closePriceRaw")
        or strip_comma_number(data.get("stockEndPrice"))
        or strip_comma_number(data.get("closePrice"))
    )
    return (float(raw) if raw else 0.0, None)  # basic 응답엔 체결 일시 필드 없음.


def _parse_yahoo_chart_price(data: dict) -> tuple[float, str | None]:
    """Yahoo chart v8: chart.result[0].meta.regularMarketPrice (+regularMarketTime epoch)."""
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return (0.0, None)
    meta = result[0].get("meta") or {}
    raw = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime")
    traded_on = (
        datetime.fromtimestamp(ts, KST).date().isoformat()
        if isinstance(ts, (int, float)) and ts > 0
        else None
    )
    return (float(raw) if raw else 0.0, traded_on)


async def _try_endpoint(
    client: httpx.AsyncClient,
    url: str,
    parse_price: Callable[[dict], tuple[float, str | None]],
    log_label: str,
    code: str,
) -> QuoteResult | None:
    try:
        res = await client.get(url, headers=_HEADERS, timeout=QUOTE_ATTEMPT_TIMEOUT)
        if res.status_code == 200:
            price, traded_on = parse_price(res.json())
            if price > 0:
                return {
                    "price": price,
                    "currency": CURRENCY_KRW,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                    "traded_on": traded_on,
                }
    except Exception:
        logger.warning("%s 시세 실패 code=%s", log_label, code, exc_info=True)
    return None


async def _fetch_naver(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    """Naver 공급자 — realtime → basic 2단계는 내부 구현 디테일."""
    result = await _try_endpoint(
        client,
        NAVER_REALTIME_URL.format(code=code),
        _parse_realtime_price,
        "naver realtime",
        code,
    )
    if result is not None:
        return result
    return await _try_endpoint(
        client,
        NAVER_BASIC_URL.format(code=code),
        _parse_basic_price,
        "naver basic",
        code,
    )


async def _fetch_yahoo(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    """Yahoo 공급자 — KOSPI(.KS) → KOSDAQ(.KQ) 순 시도.

    market 정보가 없어 두 suffix 모두 확인. 둘 다 200을 주더라도 잘못된 시장은
    result.length=0 이라 _parse_yahoo_chart_price 가 0.0 을 반환하여 자동 스킵.
    """
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


# 시세 공급자 registry — env QUOTE_PROVIDERS 의 이름이 여기 등록돼 있어야 한다.
# 새 공급자(예: kis) 추가 시 fetch 함수 작성 후 여기 등록하면 env 로 전환 가능.
_QUOTE_REGISTRY: dict[str, Callable] = {
    "naver": _fetch_naver,
    "yahoo": _fetch_yahoo,
}

# 기본 체인 — config.DEFAULT_QUOTE_PROVIDERS 단일 출처(Settings 기본값과 drift 방지).
_DEFAULT_QUOTE_PROVIDERS = DEFAULT_QUOTE_PROVIDERS


def validate_quote_providers(providers: Sequence[str]) -> None:
    """env QUOTE_PROVIDERS 오타를 앱 startup 에서 fail-fast 로 검증.

    요청 경로는 fetch_quotes_by_keys 의 gather(return_exceptions=True) 가 ValueError 를
    삼켜 전 종목 시세가 조용히 null 이 되므로, lifespan 에서 미리 검증해야 한다.
    """
    resolve_chain(providers, _QUOTE_REGISTRY, domain="quotes")


async def _fetch_kr_price(
    client: httpx.AsyncClient,
    code: str,
    providers: Sequence[str] = _DEFAULT_QUOTE_PROVIDERS,
) -> QuoteResult | None:
    for fetch in resolve_chain(providers, _QUOTE_REGISTRY, domain="quotes"):
        result = await fetch(client, code)
        if result is not None:
            return result
    return None


async def _get_cached(
    state: QuoteCacheState, key: str, fetch_fn, *, force_refresh: bool = False
) -> dict | None:
    """동일 키 동시 요청은 single-flight — 첫 호출자만 fetch_fn 실행.

    force_refresh=True 면 캐시 hit 을 무시하고 새로 fetch 한다 (단, 진행 중인 fetch 가
    있으면 stampede 회피를 위해 그 결과를 공유). fetch 는 QUOTE_FETCH_DEADLINE 으로 캡.
    """
    async with state.lock:
        if not force_refresh and key in state.cache:
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
        result = await asyncio.wait_for(fetch_fn(), QUOTE_FETCH_DEADLINE)
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
    force_refresh: bool = False,
    providers: Sequence[str] = _DEFAULT_QUOTE_PROVIDERS,
) -> dict[str, QuoteResult | None]:
    """keys 형식: "종목코드:국가" (예: "005930:KR"). KR 외 국가는 MVP에서 null.

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 lifespan-managed 공유 인스턴스.
    `force_refresh=True` (pull-to-refresh) 면 캐시를 우회해 새 시세를 받는다.
    `providers` 는 호출측(라우터)이 settings.quote_provider_list 를 전달 — 내부에서
    get_settings() 를 읽지 않는다(테스트 격리·암묵 의존 방지).
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
            lambda code=e["code"]: _fetch_kr_price(client, code, providers),
            force_refresh=force_refresh,
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
