"""일별 종가 적재 — data.go.kr getStockPriceInfo 범위 조회 + watermark 증분 backfill.

자산 변화 페이지가 과거 종가를 daily_close_prices 에서 읽고, 결측 구간만 이 모듈이 채운다.
fetch 유틸(`_get_with_retry`/`_extract_items`/`_basdt_to_date`)은 stock_seed.py 와 공유한다.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import asyncpg
import httpx

from invest_note_api.db_ops import daily_prices_repo
from invest_note_api.external.constants import USER_AGENT
from invest_note_api.services.stock_seed import (
    _DATA_GO_KR_TIMEOUT,
    _basdt_to_date,
    _extract_items,
    _get_with_retry,
)

# 주식시세(15094808) getStockPriceInfo — likeSrtnCd + beginBasDt/endBasDt 범위 조회 지원.
# 응답은 거래일만 반환(주말/휴장 자동 제외). item 키: basDt, clpr(종가), srtnCd(6자리, 'A' 없음).
_STOCK_PRICE_URL = (
    "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
)
# 증권상품시세(15094806) — ETF/ETN 은 주식 엔드포인트에 없으므로 별도 오퍼레이션을 쓴다.
# 파라미터(likeSrtnCd/beginBasDt/endBasDt)·응답 필드(srtnCd/clpr/basDt)는 주식과 동일.
_SECURITIES_PRODUCT_BASE = (
    "https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService"
)
_ETF_PRICE_URL = f"{_SECURITIES_PRODUCT_BASE}/getETFPriceInfo"
_ETN_PRICE_URL = f"{_SECURITIES_PRODUCT_BASE}/getETNPriceInfo"
_PAGE_SIZE = 1000


def _price_url_for_market(market: str | None) -> str:
    """종목 마켓(stocks.market)에 맞는 일별 시세 엔드포인트. ETF/ETN 은 증권상품시세, 그 외는 주식시세."""
    m = (market or "").upper()
    if m == "ETF":
        return _ETF_PRICE_URL
    if m == "ETN":
        return _ETN_PRICE_URL
    return _STOCK_PRICE_URL


def _normalize_ticker(raw: str | None) -> str:
    """srtnCd → 6자리 종목코드(앞 'A' 제거 후 끝 6자리). stock_seed 와 동일 규칙."""
    return (raw or "").strip().lstrip("A")[-6:]


def _parse_close_item(it: dict, ticker: str) -> dict | None:
    """getStockPriceInfo item → {ticker, close_date, close_price}.

    likeSrtnCd 는 부분일치라 다른 종목이 섞여 올 수 있다 → srtnCd 정규화 후 ticker 정확 일치만 채택.
    clpr(종가)·basDt 결측/파싱불가는 None(해당 행 skip).
    """
    if _normalize_ticker(it.get("srtnCd")) != ticker:
        return None
    close_date = _basdt_to_date((it.get("basDt") or "").strip() or None)
    if close_date is None:
        return None
    raw = it.get("clpr")
    raw = raw.strip() if isinstance(raw, str) else raw
    if raw in (None, ""):
        return None
    try:
        close_price = float(raw)
    except (TypeError, ValueError):
        return None
    return {"ticker": ticker, "close_date": close_date, "close_price": close_price}


async def fetch_daily_closes(
    api_key: str,
    ticker: str,
    begin: date,
    end: date,
    *,
    url: str = _STOCK_PRICE_URL,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """단일 종목의 [begin, end] 일별 종가를 범위 조회로 수집.

    `url` 로 엔드포인트를 선택한다(주식=getStockPriceInfo, ETF/ETN=getETF/ETNPriceInfo).
    반환: [{ticker, close_date(date), close_price(float)}] (거래일만, srtnCd 정확 일치만).
    게이트웨이 간헐 404/타임아웃은 _get_with_retry 가 흡수한다. 페이징.
    """
    norm = _normalize_ticker(ticker)
    base_params = {
        "serviceKey": api_key,
        "resultType": "json",
        "numOfRows": _PAGE_SIZE,
        "likeSrtnCd": norm,
        "beginBasDt": begin.strftime("%Y%m%d"),
        "endBasDt": end.strftime("%Y%m%d"),
    }

    rows: list[dict] = []

    async def _run(c: httpx.AsyncClient) -> None:
        page = 1
        while True:
            res = await _get_with_retry(
                c, url, {**base_params, "pageNo": page}
            )
            items = _extract_items(res.json())
            if not items:
                break
            rows.extend(r for it in items if (r := _parse_close_item(it, norm)))
            if len(items) < _PAGE_SIZE:
                break
            page += 1

    if client is None:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT
        ) as owned:
            await _run(owned)
    else:
        await _run(client)
    return rows


async def backfill_closes(
    conn: Any,
    api_key: str,
    tickers: list[str],
    earliest: date,
    today: date,
    *,
    country_code: str = "KR",
) -> bool:
    """종목별 watermark 이후~어제 구간만 fetch→upsert. 종목 단위 실패는 skip.

    - 각 종목: begin = max(earliest, watermark+1일), end = 어제(today-1). 적재 종료일은 어제
      (오늘은 라이브 시세 사용 — 적재 안 함).
    - begin > end 면 채울 게 없으므로 skip(이미 최신).
    - 종목 fetch 실패는 그 종목만 건너뛰고 incomplete 플래그를 세운다(부분 표시).

    반환: incomplete (하나라도 fetch 실패해 결측 가능 시 True).
    """
    if not tickers or not api_key:
        return bool(tickers) and not api_key  # 키 없으면 적재 불가 → 종목 있으면 incomplete

    yesterday = today - timedelta(days=1)
    if earliest > yesterday:
        return False  # 적재 대상 과거 구간 없음(오늘만 관심).

    watermarks = await daily_prices_repo.get_watermarks(
        conn, tickers, country_code=country_code
    )
    # 종목 마켓 조회 → ETF/ETN 은 증권상품시세, 그 외는 주식시세 엔드포인트로 라우팅.
    market_rows = await conn.fetch(
        "select ticker, market from stocks where country_code = $1 and ticker = any($2::text[])",
        country_code,
        list(tickers),
    )
    market_of = {r["ticker"]: r["market"] for r in market_rows}
    incomplete = False

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT
    ) as client:
        for ticker in tickers:
            wm = watermarks.get(ticker)
            begin = max(earliest, wm + timedelta(days=1)) if wm else earliest
            if begin > yesterday:
                continue  # 이 종목은 이미 어제까지 적재됨.
            try:
                rows = await fetch_daily_closes(
                    api_key,
                    ticker,
                    begin,
                    yesterday,
                    url=_price_url_for_market(market_of.get(ticker)),
                    client=client,
                )
            except Exception:
                incomplete = True  # 이 종목 결측 가능 → 부분 표시.
                continue
            if rows:
                await daily_prices_repo.upsert_closes(
                    conn, rows, country_code=country_code
                )

    return incomplete


async def prune_older_than(
    conn: Any, cutoff: date, *, country_code: str = "KR"
) -> int:
    """cutoff 이전 종가 삭제(2년 윈도우 유지). repo 위임."""
    return await daily_prices_repo.prune_older_than(
        conn, cutoff, country_code=country_code
    )


# ─────────────────────────── 사전 적재(전체 유저 보유종목 union) ───────────────────────────

_LOOKBACK_DAYS = 365 * 2


async def seed_daily_prices(db_url: str, *, api_key: str) -> None:
    """전체 유저 보유종목 union 의 2년치 종가를 사전 적재(cron pre-warm).

    콜드스타트 백필 지연 완화용. seed_stocks 와 동일하게 자체 asyncpg.connect 로 동작한다 —
    backfill 이 data.go.kr 를 길게 호출하므로 요청 풀을 차용하지 않는다(풀 고갈 방지).
    trades 는 RLS 가 걸려있으나 service-role connect 는 RLS 를 우회하므로 전체 유저 종목을 본다.
    """
    today = date.today()
    earliest = today - timedelta(days=_LOOKBACK_DAYS)
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        rows = await conn.fetch(
            "select distinct ticker_symbol from trades "
            "where ticker_symbol is not null and ticker_symbol <> ''"
        )
        tickers = [r["ticker_symbol"] for r in rows]
        if not tickers:
            return
        await backfill_closes(conn, api_key, tickers, earliest, today)
        # 2년 윈도우 유지 — 오래된 종가 정리.
        await prune_older_than(conn, earliest)
    finally:
        await conn.close()
