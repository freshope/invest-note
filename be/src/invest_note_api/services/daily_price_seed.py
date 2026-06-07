"""일별 종가 적재 — data.go.kr getStockPriceInfo 범위 조회 + watermark 증분 backfill.

자산 변화 페이지가 과거 종가를 daily_close_prices 에서 읽고, 결측 구간만 이 모듈이 채운다.
data.go.kr 는 T+1(~14:00 KST) 발행이라 어제 종가가 비는 tail-gap 이 생긴다 — 이 구간만
네이버 일별 캔들(T+0 반영)로 보충한다(`fetch_naver_daily_closes`).
fetch 유틸(`_get_with_retry`/`_extract_items`/`_basdt_to_date`)은 stock_seed.py 와 공유한다.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import asyncpg
import httpx

from invest_note_api.db_ops import daily_prices_repo
from invest_note_api.domain.asset_history import LOOKBACK_DAYS
from invest_note_api.external.constants import KIS_DAILY_CHART_PATH, USER_AGENT
from invest_note_api.external.kis import kis_get
from invest_note_api.external.provider_registry import resolve_chain
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
# 네이버 일별 캔들 — data.go.kr T+1 발행 전 tail-gap 보충용. 거래일만 반환(주말/휴장 제외).
# 주식/ETF 동일 경로(KR 전용). item 키: localDate(YYYYMMDD), closePrice(float).
_NAVER_DAILY_CHART_URL = "https://api.stock.naver.com/chart/domestic/item/{code}/day"
_PAGE_SIZE = 1000
# data.go.kr 동시 호출 상한(게이트웨이 429 가드). stock_seed._NAVER_CONCURRENCY 선례.
_BACKFILL_CONCURRENCY = 8
# 어제까지 조회 완료(빈 응답 포함)한 종목의 재probe 쿨다운. 짧으면 늦은 발행(T+1 ~14:00 KST)을
# 빨리 반영하나 호출 수↑, 길면 호출↓·반영 지연↑. 오늘 점은 라이브 시세라 과거 점만 영향.
_BACKFILL_RECHECK_COOLDOWN = timedelta(hours=6)


def _price_url_for_market(market: str | None) -> str:
    """종목 마켓(stocks.market)에 맞는 일별 시세 엔드포인트. ETF/ETN 은 증권상품시세, 그 외는 주식시세."""
    m = (market or "").upper()
    if m == "ETF":
        return _ETF_PRICE_URL
    if m == "ETN":
        return _ETN_PRICE_URL
    return _STOCK_PRICE_URL


# 일별 종가 공급자 registry — env DAILY_PRICE_PROVIDER / DAILY_PRICE_GAP_PROVIDER 의 이름이
# 여기 등록돼 있어야 한다. primary 는 (api_key, ticker, begin, end, market, client) 시그니처,
# gap 은 (client, ticker, begin, end) 시그니처. 정의는 함수 선언 뒤(모듈 하단 근처) 참조.
_GAP_DISABLED = ("", "none")  # gap_provider 비활성 값


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


async def fetch_naver_daily_closes(
    client: httpx.AsyncClient, ticker: str, begin: date, end: date
) -> list[dict]:
    """네이버 일별 캔들에서 [begin, end] 종가 수집 — data.go.kr 미발행(T+1) tail-gap 보충용.

    반환 형태는 fetch_daily_closes 와 동일: [{ticker, close_date, close_price}].
    ETN 등 이 경로 미지원 종목은 빈 배열 → 보충 없음(data.go.kr 발행 후 자연 수렴).
    """
    norm = _normalize_ticker(ticker)
    res = await client.get(
        _NAVER_DAILY_CHART_URL.format(code=norm),
        params={
            "startDateTime": begin.strftime("%Y%m%d") + "000000",
            "endDateTime": end.strftime("%Y%m%d") + "000000",
        },
    )
    res.raise_for_status()
    items = res.json()
    if not isinstance(items, list):
        return []
    rows: list[dict] = []
    for it in items:
        close_date = _basdt_to_date((it.get("localDate") or "").strip() or None)
        raw = it.get("closePrice")
        if close_date is None or raw in (None, ""):
            continue
        try:
            close_price = float(raw)
        except (TypeError, ValueError):
            continue
        # 범위 밖 행 가드 — watermark 가 어제 너머로 오르는 오염 방지.
        if begin <= close_date <= end:
            rows.append({"ticker": norm, "close_date": close_date, "close_price": close_price})
    return rows


async def fetch_kis_daily_closes(
    client: httpx.AsyncClient, ticker: str, begin: date, end: date
) -> list[dict]:
    """KIS 기간별 시세(FHKST03010100)에서 [begin, end] 일별 종가 수집.

    호출당 최대 100건을 최근일부터 역순 반환 → end 커서를 가장 오래된 행 직전일로
    당기며 구간 분할 페이징. 반환 형태는 fetch_daily_closes 와 동일.
    오류 응답/토큰 실패(kis_get None)는 예외 — primary 계약상 실패는 raise 해야
    backfill 이 sync_state 를 기록하지 않고 다음 요청에 재시도한다.
    """
    norm = _normalize_ticker(ticker)
    rows: list[dict] = []
    end_cursor = end
    # 2년 LOOKBACK ≈ 거래일 ~500건(100건×5호출) — 여유 상한으로 무한 루프 가드.
    for _ in range(30):
        if end_cursor < begin:
            break
        body = await kis_get(
            client,
            KIS_DAILY_CHART_PATH,
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",  # KRX (주식/ETF/ETN 통합)
                "FID_INPUT_ISCD": norm,
                "FID_INPUT_DATE_1": begin.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_cursor.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1",  # 원주가 — data.go.kr clpr(발행 당시 가격)과 일관
            },
        )
        if body is None:
            raise RuntimeError(f"KIS 일별 종가 조회 실패 ticker={norm}")
        page: list[dict] = []
        for it in body.get("output2") or []:
            close_date = _basdt_to_date((it.get("stck_bsop_date") or "").strip() or None)
            raw = it.get("stck_clpr")
            if close_date is None or raw in (None, ""):
                continue
            try:
                close_price = float(raw)
            except (TypeError, ValueError):
                continue
            # 범위 밖 행 가드 — watermark 가 어제 너머로 오르는 오염 방지.
            if begin <= close_date <= end_cursor:
                page.append(
                    {"ticker": norm, "close_date": close_date, "close_price": close_price}
                )
        if not page:
            break  # 빈 구간(휴장/상장 전) — 더 과거로 내려갈 데이터 없음.
        rows.extend(page)
        oldest = min(r["close_date"] for r in page)
        if oldest <= begin:
            break
        end_cursor = oldest - timedelta(days=1)
    return rows


async def _fetch_data_go_kr_closes(
    api_key: str,
    ticker: str,
    begin: date,
    end: date,
    *,
    market: str | None,
    client: httpx.AsyncClient,
) -> list[dict]:
    """data.go.kr primary 공급자 — 종목 마켓별 엔드포인트 라우팅은 내부 구현 디테일."""
    return await fetch_daily_closes(
        api_key, ticker, begin, end, url=_price_url_for_market(market), client=client
    )


async def _fetch_naver_gap_closes(
    client: httpx.AsyncClient, ticker: str, begin: date, end: date
) -> list[dict]:
    """naver gap 공급자 — 모듈 전역을 런타임 조회(late-binding)해 테스트 monkeypatch 를 존중."""
    return await fetch_naver_daily_closes(client, ticker, begin, end)


async def _fetch_kis_primary_closes(
    api_key: str,
    ticker: str,
    begin: date,
    end: date,
    *,
    market: str | None,
    client: httpx.AsyncClient,
) -> list[dict]:
    """kis primary 공급자 — api_key(data.go.kr 전용)·market("J" 통합 시장코드) 미사용."""
    return await fetch_kis_daily_closes(client, ticker, begin, end)


async def _fetch_kis_gap_closes(
    client: httpx.AsyncClient, ticker: str, begin: date, end: date
) -> list[dict]:
    """kis gap 공급자 — KIS 일봉은 T+0 반영이라 tail-gap 보충에도 사용 가능."""
    return await fetch_kis_daily_closes(client, ticker, begin, end)


# 공급자 registry — 새 공급자 추가 시 여기 등록하면 env 변경만으로 전환 가능.
_PRIMARY_REGISTRY = {"data_go_kr": _fetch_data_go_kr_closes, "kis": _fetch_kis_primary_closes}
_GAP_REGISTRY = {"naver": _fetch_naver_gap_closes, "kis": _fetch_kis_gap_closes}


async def backfill_closes(
    conn: Any,
    api_key: str,
    tickers: list[str],
    earliest: date,
    today: date,
    *,
    country_code: str = "KR",
    primary_provider: str = "data_go_kr",
    gap_provider: str = "naver",
) -> bool:
    """종목별 결측 구간(watermark 이후~어제)만 fetch→upsert. 종목 fetch 는 병렬.

    `primary_provider`/`gap_provider` 는 env(DAILY_PRICE_PROVIDER/DAILY_PRICE_GAP_PROVIDER)에서
    호출측이 전달 — 내부에서 get_settings() 를 읽지 않는다. gap_provider 가 "none"/빈 값이면
    tail-gap 보충 비활성.

    skip 규칙(종목별):
      - begin = max(earliest, watermark+1일). watermark = 적재된 실데이터 max(close_date).
      - begin > 어제 → skip(실데이터로 어제까지 채움 — 정상 평일).
      - sync_state.checked_through_date >= 어제 이고 checked_at 이 쿨다운 내 → skip
        (휴장/빈 범위를 최근 확인함 → data.go.kr 불필요. 빈 응답이 watermark 를 못 올려
         매 요청 재질의하던 문제를 차단).
      - 그 외 → fetch 대상.

    tail-gap 보충(KR): data.go.kr 가 T+1 발행이라 어제 종가가 빈다 → 그 공백 구간만
    네이버 일별 캔들로 보충해 같은 upsert 로 적재. 보충되면 watermark 가 올라가
    data.go.kr 가 그 날짜를 다시 덮지 않는다(종가 값 동일 — 수정주가 코너케이스만 갈릴 수 있음).

    단계 분리(asyncpg 단일 커넥션은 동시 쿼리 불가):
      1) DB 순차 — watermark/sync_state/market 일괄 조회.
      2) 네트워크 병렬 — Semaphore 로 동시성 제한해 fetch_daily_closes.
      3) DB 순차 — upsert_closes + upsert_sync_state.

    sync_state 는 fetch 성공(빈 응답 포함) 시에만 기록한다 — 실패(예외)는 미기록해 다음 요청
    재시도를 보장한다.

    반환: incomplete (하나라도 fetch 실패해 결측 가능 시 True).
    """
    if not tickers or not api_key:
        return bool(tickers) and not api_key  # 키 없으면 적재 불가 → 종목 있으면 incomplete

    # 공급자 해석 — unknown 이름은 ValueError(fail-fast). gap 은 비활성 값 허용.
    primary_fetch = resolve_chain([primary_provider], _PRIMARY_REGISTRY, domain="daily_price")[0]
    gap_fetch = (
        None
        if gap_provider in _GAP_DISABLED
        else resolve_chain([gap_provider], _GAP_REGISTRY, domain="daily_price_gap")[0]
    )

    yesterday = today - timedelta(days=1)
    if earliest > yesterday:
        return False  # 적재 대상 과거 구간 없음(오늘만 관심).

    # 1) DB 순차 — 상태 일괄 조회.
    watermarks = await daily_prices_repo.get_watermarks(
        conn, tickers, country_code=country_code
    )
    sync_state = await daily_prices_repo.get_sync_state(
        conn, tickers, country_code=country_code
    )
    # 종목 마켓 조회 → ETF/ETN 은 증권상품시세, 그 외는 주식시세 엔드포인트로 라우팅.
    market_rows = await conn.fetch(
        "select ticker, market from stocks where country_code = $1 and ticker = any($2::text[])",
        country_code,
        list(tickers),
    )
    market_of = {r["ticker"]: r["market"] for r in market_rows}

    now = datetime.now(timezone.utc)
    to_fetch: list[tuple[str, date]] = []
    for ticker in tickers:
        wm = watermarks.get(ticker)
        begin = max(earliest, wm + timedelta(days=1)) if wm else earliest
        if begin > yesterday:
            continue  # 실데이터로 어제까지 적재됨.
        st = sync_state.get(ticker)
        if (
            st
            and st["checked_through_date"] >= yesterday
            and now - st["checked_at"] < _BACKFILL_RECHECK_COOLDOWN
        ):
            continue  # 어제까지 최근 확인함(빈 범위) → 쿨다운 내 재질의 안 함.
        to_fetch.append((ticker, begin))

    if not to_fetch:
        return False

    # 2) 네트워크 병렬 — fetch 만 동시 실행(conn 미사용). Semaphore 로 게이트웨이 보호.
    sem = asyncio.Semaphore(_BACKFILL_CONCURRENCY)

    async def _fetch_one(
        ticker: str, begin: date, client: httpx.AsyncClient
    ) -> tuple[str, list[dict] | None, bool]:
        """반환: (ticker, rows, synced). synced=False 면 sync_state 미기록(다음 요청 재시도)."""
        async with sem:
            try:
                rows = await primary_fetch(
                    api_key,
                    ticker,
                    begin,
                    yesterday,
                    market=market_of.get(ticker),
                    client=client,
                )
            except Exception:
                return ticker, None, False  # 실패 → sync_state 미기록(다음 요청 재시도).
            # tail-gap 보충: primary 가 어제까지 못 채운 구간을 gap 공급자로(KR 전용 경로).
            if gap_fetch is not None and country_code == "KR":
                gap_begin = (
                    max((r["close_date"] for r in rows), default=begin - timedelta(days=1))
                    + timedelta(days=1)
                )
                if gap_begin <= yesterday:
                    try:
                        rows = rows + await gap_fetch(client, ticker, gap_begin, yesterday)
                    except Exception:
                        # primary 분은 upsert 하되 상태 미기록 → 보충 재시도 보장.
                        return ticker, rows, False
            return ticker, rows, True

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT
    ) as client:
        results = await asyncio.gather(
            *(_fetch_one(tk, bg, client) for tk, bg in to_fetch)
        )

    # 3) DB 순차 — upsert + sync_state. 실패 종목은 incomplete + 상태 미기록.
    # 종목별 rows 를 모아 단일 executemany 로 배치(왕복 N→1).
    incomplete = False
    all_rows: list[dict] = []
    state_rows: list[dict] = []
    for ticker, rows, synced in results:
        if rows is None:
            incomplete = True
            continue
        all_rows.extend(rows)
        if synced:
            state_rows.append({"ticker": ticker, "checked_through_date": yesterday})
        else:
            incomplete = True  # 네이버 보충 실패 — 어제 점 결측 가능.
    if all_rows:
        await daily_prices_repo.upsert_closes(
            conn, all_rows, country_code=country_code
        )
    if state_rows:
        await daily_prices_repo.upsert_sync_state(
            conn, state_rows, country_code=country_code
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

async def seed_daily_prices(
    db_url: str,
    *,
    api_key: str,
    primary_provider: str = "data_go_kr",
    gap_provider: str = "naver",
) -> None:
    """전체 유저 보유종목 union 의 2년치 종가를 사전 적재(cron pre-warm).

    콜드스타트 백필 지연 완화용. seed_stocks 와 동일하게 자체 asyncpg.connect 로 동작한다 —
    backfill 이 data.go.kr 를 길게 호출하므로 요청 풀을 차용하지 않는다(풀 고갈 방지).
    trades 는 RLS 가 걸려있으나 service-role connect 는 RLS 를 우회하므로 전체 유저 종목을 본다.
    """
    today = date.today()
    earliest = today - timedelta(days=LOOKBACK_DAYS)
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        rows = await conn.fetch(
            "select distinct ticker_symbol from trades "
            "where ticker_symbol is not null and ticker_symbol <> ''"
        )
        tickers = [r["ticker_symbol"] for r in rows]
        if not tickers:
            return
        await backfill_closes(
            conn,
            api_key,
            tickers,
            earliest,
            today,
            primary_provider=primary_provider,
            gap_provider=gap_provider,
        )
        # 2년 윈도우 유지 — 오래된 종가 정리.
        await prune_older_than(conn, earliest)
    finally:
        await conn.close()
