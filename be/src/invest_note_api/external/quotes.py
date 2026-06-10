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
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from cachetools import TTLCache
from fastapi import Request

from invest_note_api.config import DEFAULT_QUOTE_PROVIDERS
from invest_note_api.domain.trade_types import COUNTRY_US, DEFAULT_COUNTRY, MAX_CODE_LEN
from invest_note_api.domain.trade_utils import KST, position_key
from invest_note_api.external.constants import (
    CURRENCY_KRW,
    CURRENCY_USD,
    KIS_INQUIRE_PRICE_PATH,
    NAVER_BASIC_URL,
    NAVER_REALTIME_URL,
    QUOTE_ATTEMPT_TIMEOUT,
    QUOTE_CACHE_MAXSIZE,
    QUOTE_CACHE_TTL,
    QUOTE_FETCH_DEADLINE,
    USER_AGENT,
    YAHOO_CHART_URL,
)
from invest_note_api.external.kis import kis_get
from invest_note_api.external.provider_registry import resolve_chain
from invest_note_api.utils.numbers import strip_comma_number

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}

# US 티커가 Yahoo chart URL 경로에 그대로 들어가므로 `/`·`?`·`#` 조작(trust-boundary)을 막는
# 화이트리스트. 영숫자/`.`(클래스주)/`-`(BRK-B 표기) 1~20자만 허용.
_US_TICKER_PATTERN = re.compile(r"[A-Za-z0-9.\-]{1,20}")


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


async def _fetch_yahoo_us(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    """Yahoo 해외(US) 시세 — suffix 없는 티커. 통화는 응답 meta.currency 를 사용(USD fallback).

    KR 경로(`_fetch_yahoo`)는 currency 를 KRW 로 고정하지만, 해외는 종목별 통화가 다를 수
    있어 meta 의 통화를 그대로 신뢰한다.

    사용자 입력 심볼이 URL 경로에 그대로 들어가므로, 화이트리스트(_US_TICKER_PATTERN)에
    불일치하는 code 는 graceful null(기존 fetch 실패 == None 계약과 일관)로 거른다.
    """
    if not _US_TICKER_PATTERN.fullmatch(code):
        return None
    try:
        res = await client.get(
            YAHOO_CHART_URL.format(symbol=code), headers=_HEADERS, timeout=QUOTE_ATTEMPT_TIMEOUT
        )
    except Exception:
        logger.warning("yahoo us 시세 실패 code=%s", code, exc_info=True)
        return None
    if res.status_code != 200:
        return None
    data = res.json()
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return None
    meta = result[0].get("meta") or {}
    price, traded_on = _parse_yahoo_chart_price(data)
    if price <= 0:
        return None
    return {
        "price": price,
        "currency": meta.get("currency") or CURRENCY_USD,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "traded_on": traded_on,
    }


# KIS 레이트리밋(실측 2건/초) 슬롯 대기 예산 — 멀티 종목 동시 시세에서 슬롯을 못 얻은
# 종목은 빠르게 다음 공급자(naver)로 넘어가야 전체 deadline(QUOTE_FETCH_DEADLINE) 안에 든다.
_KIS_QUOTE_THROTTLE_BUDGET = 1.0


async def _fetch_kis(client: httpx.AsyncClient, code: str) -> QuoteResult | None:
    """KIS 공급자 — 국내주식 현재가(FHKST01010100). 시장구분 "J"(주식/ETF/ETN 통합).

    자격증명 미설정·토큰 발급 실패·오류 응답·레이트리밋 슬롯 부족은 kis_get 이
    None 으로 수렴시켜 다음 공급자로 fallback 한다. 응답에 체결 일시 필드가 없어
    traded_on 은 None.
    """
    body = await kis_get(
        client,
        KIS_INQUIRE_PRICE_PATH,
        tr_id="FHKST01010100",
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        timeout=QUOTE_ATTEMPT_TIMEOUT,
        throttle_budget=_KIS_QUOTE_THROTTLE_BUDGET,
    )
    if body is None:
        return None
    raw = (body.get("output") or {}).get("stck_prpr")
    try:
        price = float(raw) if raw else 0.0
    except (TypeError, ValueError):
        price = 0.0
    if price <= 0:
        return None
    return {
        "price": price,
        "currency": CURRENCY_KRW,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "traded_on": None,
    }


# 시세 공급자 registry — env QUOTE_PROVIDERS 의 이름이 여기 등록돼 있어야 한다.
# 새 공급자 추가 시 fetch 함수 작성 후 여기 등록하면 env 로 전환 가능.
_QUOTE_REGISTRY: dict[str, Callable] = {
    "naver": _fetch_naver,
    "yahoo": _fetch_yahoo,
    "kis": _fetch_kis,
}


def validate_quote_providers(providers: Sequence[str]) -> None:
    """env QUOTE_PROVIDERS 오타를 앱 startup 에서 fail-fast 로 검증.

    요청 경로는 fetch_quotes_by_keys 의 gather(return_exceptions=True) 가 ValueError 를
    삼켜 전 종목 시세가 조용히 null 이 되므로, lifespan 에서 미리 검증해야 한다.
    빈 체인(QUOTE_PROVIDERS="")도 같은 이유로 거부 — resolve_chain([]) 은 안 던진다.
    """
    if not providers:
        raise ValueError("quotes: 공급자 체인이 비어 있습니다 (QUOTE_PROVIDERS 확인)")
    resolve_chain(providers, _QUOTE_REGISTRY, domain="quotes")


async def _fetch_kr_price(
    client: httpx.AsyncClient,
    code: str,
    providers: Sequence[str] = DEFAULT_QUOTE_PROVIDERS,
) -> QuoteResult | None:
    for fetch in resolve_chain(providers, _QUOTE_REGISTRY, domain="quotes"):
        result = await fetch(client, code)
        if result is not None:
            return result
    return None


def _entry_fetch_fn(
    country: str,
    code: str,
    client: httpx.AsyncClient,
    providers: Sequence[str],
) -> Callable[[], Awaitable[QuoteResult | None]] | None:
    """국가별 시세 fetch 콜러블. 공급자가 없는 국가는 None(→ 결과 null)."""
    if country == DEFAULT_COUNTRY:
        return lambda: _fetch_kr_price(client, code, providers)
    if country == COUNTRY_US:
        return lambda: _fetch_yahoo_us(client, code)
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
        # fetch 실패/빈결과(None)는 캐시에 박지 않는다 — 일시 장애 1회가 TTL(45s) 동안
        # 해외 평가액을 통째로 가리는 것을 막는다. 직전 성공값(non-None)이 있으면 stale 로
        # 유지·반환(현재·후속 호출자 모두), 없으면 None 그대로 다음 요청에서 재시도.
        # "원래 시세 없는 종목"은 직전값도 None 이라 여전히 None — 영향 없음.
        # (fx.get_fx_rate 의 실패-시-stale-유지와 동일 사상. stale 무한 유지는 TTLCache 자연 만료로 차단.)
        prior = state.cache.get(key)
        if result is None and prior is not None:
            result = prior
        elif result is not None:
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
    providers: Sequence[str] = DEFAULT_QUOTE_PROVIDERS,
) -> dict[str, QuoteResult | None]:
    """keys 형식: "종목코드:국가" (예: "005930:KR", "AAPL:US"). KR→공급자 체인, US→Yahoo.

    KR/US 외 국가(OTHER 등)는 공급자가 없어 null. `client` 는 라우터의
    `Depends(get_http_client)` 로 주입받은 lifespan-managed 공유 인스턴스.
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

    task_entries = []
    tasks = []
    for e in entries:
        fetch_fn = _entry_fetch_fn(e["country"], e["code"], client, providers)
        if fetch_fn is None:
            continue  # 공급자 없는 국가 → out 기본값 None 유지
        task_entries.append(e)
        tasks.append(
            _get_cached(
                state,
                position_key(e["code"], e["country"]),
                fetch_fn,
                force_refresh=force_refresh,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: dict[str, QuoteResult | None] = {e["key"]: None for e in entries}
    for e, result in zip(task_entries, results):
        out[e["key"]] = None if isinstance(result, Exception) else result

    return out
