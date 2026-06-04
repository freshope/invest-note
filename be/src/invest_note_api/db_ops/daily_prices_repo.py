"""asyncpg 쿼리 묶음 — daily_close_prices(일별 종가) 조회/적재.

전역 참조 데이터(RLS 미적용)라 user 컨텍스트 무관. asyncpg 스타일은 stocks_repo.py 따름.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from invest_note_api.domain.trade_types import DEFAULT_COUNTRY

# (country, ticker, close_date) 충돌 시 종가만 갱신(updated_at 동반). 적재 재실행 멱등.
_UPSERT_SQL = """
insert into daily_close_prices (country_code, ticker, close_date, close_price, updated_at)
values ($1, $2, $3, $4, now())
on conflict (country_code, ticker, close_date) do update set
    close_price = excluded.close_price,
    updated_at  = now()
"""

# (country, ticker) 충돌 시 조회 완료일·시각 갱신. 빈 응답도 "확인함"으로 기록(재질의 방지).
_UPSERT_SYNC_STATE_SQL = """
insert into daily_price_sync_state (country_code, ticker, checked_through_date, checked_at)
values ($1, $2, $3, now())
on conflict (country_code, ticker) do update set
    checked_through_date = excluded.checked_through_date,
    checked_at           = now()
"""


async def get_watermarks(
    conn: Any, tickers: list[str], *, country_code: str = DEFAULT_COUNTRY
) -> dict[str, date]:
    """종목별 적재된 max(close_date). 미적재 종목은 키 없음.

    backfill 이 "watermark 이후~어제만" fetch 하는 증분 적재의 기준.
    """
    if not tickers:
        return {}
    rows = await conn.fetch(
        """
        select ticker, max(close_date) as max_date
        from daily_close_prices
        where country_code = $1 and ticker = any($2::text[])
        group by ticker
        """,
        country_code,
        tickers,
    )
    return {r["ticker"]: r["max_date"] for r in rows}


async def get_sync_state(
    conn: Any, tickers: list[str], *, country_code: str = DEFAULT_COUNTRY
) -> dict[str, dict]:
    """종목별 backfill 조회 완료 상태. 반환: {ticker: {checked_through_date, checked_at}}.

    미조회 종목은 키 없음. backfill 이 "이미 어제까지 조회했고(빈 응답 포함) 쿨다운 내" 인
    종목의 data.go.kr 재질의를 skip 하는 기준.
    """
    if not tickers:
        return {}
    rows = await conn.fetch(
        """
        select ticker, checked_through_date, checked_at
        from daily_price_sync_state
        where country_code = $1 and ticker = any($2::text[])
        """,
        country_code,
        tickers,
    )
    return {
        r["ticker"]: {
            "checked_through_date": r["checked_through_date"],
            "checked_at": r["checked_at"],
        }
        for r in rows
    }


async def get_closes(
    conn: Any,
    tickers: list[str],
    begin: date,
    end: date,
    *,
    country_code: str = DEFAULT_COUNTRY,
) -> list[dict]:
    """[begin, end] 범위의 종가 행. 반환: [{ticker, close_date, close_price(float)}] (날짜 오름차순).

    asset_history 계산은 종목별 carry-forward 를 하므로 ticker, close_date 순으로 정렬해 반환한다.
    """
    if not tickers:
        return []
    rows = await conn.fetch(
        """
        select ticker, close_date, close_price
        from daily_close_prices
        where country_code = $1 and ticker = any($2::text[])
          and close_date >= $3 and close_date <= $4
        order by ticker, close_date
        """,
        country_code,
        tickers,
        begin,
        end,
    )
    return [
        {
            "ticker": r["ticker"],
            "close_date": r["close_date"],
            "close_price": float(r["close_price"]),
        }
        for r in rows
    ]


async def upsert_closes(
    conn: Any, rows: list[dict], *, country_code: str = DEFAULT_COUNTRY
) -> int:
    """종가 rows 멱등 UPSERT. rows item: {ticker, close_date(date), close_price(number)}."""
    tuples = [
        (country_code, r["ticker"], r["close_date"], r["close_price"])
        for r in rows
        if r.get("ticker") and r.get("close_date") is not None and r.get("close_price") is not None
    ]
    if not tuples:
        return 0
    await conn.executemany(_UPSERT_SQL, tuples)
    return len(tuples)


async def upsert_sync_state(
    conn: Any, rows: list[dict], *, country_code: str = DEFAULT_COUNTRY
) -> int:
    """조회 완료 상태 멱등 UPSERT. rows item: {ticker, checked_through_date(date)}.

    checked_at 은 SQL now() 로 기록한다(빈 응답이어도 "확인 시각" 전진 — 쿨다운 재probe 기준).
    """
    tuples = [
        (country_code, r["ticker"], r["checked_through_date"])
        for r in rows
        if r.get("ticker") and r.get("checked_through_date") is not None
    ]
    if not tuples:
        return 0
    await conn.executemany(_UPSERT_SYNC_STATE_SQL, tuples)
    return len(tuples)


async def prune_older_than(
    conn: Any, cutoff: date, *, country_code: str = DEFAULT_COUNTRY
) -> int:
    """cutoff 이전(close_date < cutoff) 종가 삭제. 2년 윈도우 유지용."""
    result = await conn.execute(
        "delete from daily_close_prices where country_code = $1 and close_date < $2",
        country_code,
        cutoff,
    )
    return int(result.split()[-1]) if result.startswith("DELETE") else 0
