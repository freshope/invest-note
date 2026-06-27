"""asyncpg 쿼리 묶음 — isin_ticker_map(ISIN→ticker 해소 캐시).

토스 해외(USD) import 시 OpenFIGI 로 해소한 ISIN→ticker 결과를 캐시한다.
positive(resolved=true)·negative(resolved=false, 미해결 재조회 방지) 모두 저장한다.
plain pool connection(public 테이블)로 R/W — RLS 없음.
"""
from __future__ import annotations

from typing import Any, TypedDict


class IsinCacheRow(TypedDict):
    ticker: str | None
    exch_code: str | None
    country_code: str | None
    name: str | None
    resolved: bool


_FETCH_SQL = """
select isin, ticker, exch_code, country_code, name, resolved
from isin_ticker_map
where isin = any($1::text[])
"""


async def fetch_cached(conn: Any, isins: list[str]) -> dict[str, IsinCacheRow]:
    """ISIN 목록 → {isin: 캐시행}. 캐시에 없는 ISIN 은 키 없음(→ OpenFIGI 조회 대상).

    resolved=false(negative cache) 행도 반환한다 — 호출자는 이를 캐시 hit 로 보고
    OpenFIGI 재조회를 건너뛰되, 해소로는 치지 않는다(종목명 폴백).
    """
    if not isins:
        return {}
    rows = await conn.fetch(_FETCH_SQL, isins)
    return {
        row["isin"]: {
            "ticker": row["ticker"],
            "exch_code": row["exch_code"],
            "country_code": row["country_code"],
            "name": row["name"],
            "resolved": row["resolved"],
        }
        for row in rows
    }


_UPSERT_SQL = """
insert into isin_ticker_map
    (isin, ticker, exch_code, country_code, name, resolved, source, resolved_at)
values ($1, $2, $3, $4, $5, $6, 'openfigi', now())
on conflict (isin) do update set
    ticker = excluded.ticker,
    exch_code = excluded.exch_code,
    country_code = excluded.country_code,
    name = excluded.name,
    resolved = excluded.resolved,
    source = excluded.source,
    resolved_at = now()
"""


async def upsert(conn: Any, rows: list[dict]) -> None:
    """해소/미해결 결과를 캐시에 upsert. rows: [{isin, ticker, exch_code, country_code, name, resolved}].

    멱등(PK=isin) — 재호출 시 최신 해소 결과로 갱신한다. 빈 rows 면 no-op.
    """
    if not rows:
        return
    await conn.executemany(
        _UPSERT_SQL,
        [
            (
                r["isin"],
                r["ticker"],
                r["exch_code"],
                r["country_code"],
                r["name"],
                r["resolved"],
            )
            for r in rows
        ],
    )
