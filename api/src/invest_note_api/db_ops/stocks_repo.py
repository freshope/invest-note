"""asyncpg 쿼리 묶음 — stocks 마스터 검색/매칭.

검색·일괄 import 매칭의 런타임 경로는 모두 로컬 stocks 테이블만 조회한다(외부 호출 0).
matchability(약칭/부분일치/초성)는 stock_aliases + name_chosung + pg_trgm 으로 해소한다.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypedDict

from invest_note_api.domain.hangul import is_chosung_query
from invest_note_api.domain.trade_types import COUNTRY_US, DEFAULT_COUNTRY, MAX_NAME_LEN

_MIN_QUERY_LEN = 2
_DEFAULT_LIMIT = 10


class StockSearchResult(TypedDict):
    code: str
    name: str
    market: str
    exchange: str


class StockMeta(TypedDict):
    market: str
    marcap_rank: int | None
    nps_holding: str | None
    nps_as_of: str | None
    us_index: str | None


def _row_to_result(row: Any) -> StockSearchResult:
    # 응답 shape 은 기존 Naver 검색(external/naver_search.py)과 동일하게 유지한다:
    #   market   = country_code ('KR'),  exchange = 보드 분류(KOSPI/KOSDAQ/ETF/...).
    # 주의: 보드 분류는 stocks.market 컬럼이다(stocks.exchange 는 'KRX' 운영사라 결과에 쓰지 않음).
    # trades.exchange 가 이 값을 저장하므로 어긋나면 거래 등록 데이터가 깨진다.
    return {
        "code": row["ticker"],
        "name": row["asset_name"],
        "market": row["country_code"],
        "exchange": row["market"] or "",
    }


def _escape_like(term: str) -> str:
    """LIKE/ILIKE 패턴에 들어갈 사용자 입력의 와일드카드를 이스케이프(기본 ESCAPE '\\')."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# 우선순위: 1 정확(ticker/명) > 2 명 prefix > 3 별칭 prefix > 4 초성(명+별칭) > 5 부분일치(trgm)
_SEARCH_SQL = """
with m as (
    select ticker, 1 as rank from stocks
        where country_code = $2 and is_active and (upper(ticker) = upper($1) or asset_name = $1)
    union all
    select ticker, 2 from stocks
        where country_code = $2 and is_active and asset_name ilike $5 || '%'
    union all
    select ticker, 3 from stock_aliases
        where country_code = $2 and alias ilike $5 || '%'
    union all
    select ticker, 4 from stocks
        where $4 and country_code = $2 and is_active and name_chosung like $5 || '%'
    union all
    select ticker, 4 from stock_aliases
        where $4 and country_code = $2 and alias_chosung like $5 || '%'
    union all
    select ticker, 5 from stocks
        where country_code = $2 and is_active and asset_name ilike '%' || $5 || '%'
)
select s.ticker, s.asset_name, s.country_code, s.market
from stocks s
join (select ticker, min(rank) as rank from m group by ticker) g
    on g.ticker = s.ticker
where s.country_code = $2 and s.is_active
order by g.rank, char_length(s.asset_name), s.asset_name
limit $3
"""


async def search(
    conn: Any,
    q: str,
    *,
    country_code: str = DEFAULT_COUNTRY,
    limit: int = _DEFAULT_LIMIT,
    min_len: int = 1,
) -> list[StockSearchResult]:
    """종목 검색 — ticker/명/별칭/초성/부분일치 우선순위로 최대 `limit` 건.

    `min_len` 미만 또는 > MAX_NAME_LEN 이면 빈 리스트.
    - 인터랙티브 검색은 1(사용자가 직접 고르므로 1글자 prefix 도 안전, 기존 동작 유지).
    - import 자동 매칭(`lookup_by_names`)은 2(짧은 입력의 오매칭 방지).
    """
    q = q.strip()
    if len(q) < min_len or len(q) > MAX_NAME_LEN:
        return []

    rows = await conn.fetch(
        _SEARCH_SQL,
        q,
        country_code,
        limit,
        is_chosung_query(q),
        _escape_like(q),
    )
    return [_row_to_result(row) for row in rows]


# 검색 라우터가 노출하는 국가 — KR 우선, US 후순위. 영문/한글 쿼리는 사실상 한 국가에만
# 매칭되므로 KR 결과를 먼저 채우고 남는 자리에 US 를 붙여도 실사용에서 누락이 없다.
SEARCH_COUNTRIES = (DEFAULT_COUNTRY, COUNTRY_US)


async def search_multi(
    conn: Any,
    q: str,
    *,
    countries: Sequence[str] = SEARCH_COUNTRIES,
    limit: int = _DEFAULT_LIMIT,
    min_len: int = 1,
) -> list[StockSearchResult]:
    """여러 국가에 걸쳐 종목 검색. 국가 순서대로 이어붙이고 총 `limit` 건으로 캡.

    각 결과의 `market` 필드가 country_code 라 호출측이 국가를 구분할 수 있다(ticker 가
    국가 간 충돌해도 별개 항목으로 유지).
    """
    results: list[StockSearchResult] = []
    for cc in countries:
        if len(results) >= limit:
            break
        results.extend(
            await search(conn, q, country_code=cc, limit=limit, min_len=min_len)
        )
    return results[:limit]


async def lookup_by_names(
    conn: Any,
    names: list[str],
    *,
    country_code: str = DEFAULT_COUNTRY,
) -> dict[str, StockSearchResult]:
    """종목명 목록 → {입력명: 최상위 매칭}. 미해결 종목명은 결과에서 제외(키 없음).

    일괄 import 매칭용. 각 이름을 `search` 우선순위로 1건 해소한다.
    """
    result: dict[str, StockSearchResult] = {}
    for name in names:
        matches = await search(conn, name, country_code=country_code, limit=1, min_len=_MIN_QUERY_LEN)
        if matches:
            result[name] = matches[0]
    return result


# ─────────────────────────── 종목 메타 배치 조회 (뱃지용) ───────────────────────────


_META_SQL = """
select ticker, market, marcap_rank, nps_holding, nps_as_of, us_index
from stocks
where ticker = any($1::text[])
"""


async def fetch_meta(conn: Any, codes: list[str]) -> dict[str, StockMeta]:
    """종목 코드 목록 → {code: 메타}. 매칭된 code 만 키로 포함. 빈 codes 면 DB 조회 생략.

    국가 무분기 단일 쿼리(`ticker = any($1)`). KR 6자리 숫자 ↔ US 비숫자(점/달러 포함)
    티커가 disjoint 하다는 가정에 기대 KR/US 혼재 코드를 한 번에 조회한다.
    응답 키는 snake_case 로 통일한다(/stocks/quote 와 동일하게 변환 없이 그대로 통과).
    marcap_rank 는 ETF/ETN 에서 NULL, nps_holding 은 대부분 NULL, us_index 는 SP500 편입 시 'SP500'.
    """
    if not codes:
        return {}
    rows = await conn.fetch(_META_SQL, codes)
    return {
        row["ticker"]: {
            "market": row["market"] or "",
            "marcap_rank": row["marcap_rank"],
            "nps_holding": row["nps_holding"],
            "nps_as_of": row["nps_as_of"].isoformat() if row["nps_as_of"] else None,
            "us_index": row["us_index"],
        }
        for row in rows
    }


# ─────────────────────────── 국민연금(NPS) 보유 적재 ───────────────────────────


async def reset_nps_holding(conn: Any, *, country_code: str = DEFAULT_COUNTRY) -> int:
    """전체 KR 종목의 nps_holding/nps_as_of 를 NULL 로 초기화. 새 스냅샷 재계산 직전 호출."""
    result = await conn.execute(
        "update stocks set nps_holding = null, nps_as_of = null, updated_at = now() "
        "where country_code = $1 and nps_holding is not null",
        country_code,
    )
    return int(result.split()[-1]) if result.startswith("UPDATE") else 0


async def set_nps_holding(
    conn: Any,
    tickers: set[str],
    level: str,
    as_of: Any,
    *,
    country_code: str = DEFAULT_COUNTRY,
) -> int:
    """주어진 ticker 들의 nps_holding=level, nps_as_of=as_of 설정.

    'held' 먼저 → 'major' 로 덮어쓰는 순서로 호출하면 둘 다 보유한 종목은 'major' 가 우선한다.
    """
    if not tickers:
        return 0
    result = await conn.execute(
        "update stocks set nps_holding = $3, nps_as_of = $4, updated_at = now() "
        "where country_code = $1 and ticker = any($2::text[])",
        country_code,
        list(tickers),
        level,
        as_of,
    )
    return int(result.split()[-1]) if result.startswith("UPDATE") else 0


async def upsert_nps_unmatched(conn: Any, rows: list[dict]) -> int:
    """종목명→ticker 매칭 실패분을 reconcile 큐(nps_unmatched)에 upsert.

    rows: [{nps_name, nps_as_of(date), holding_level}]. PK(nps_name, nps_as_of) 멱등.
    """
    if not rows:
        return 0
    await conn.executemany(
        "insert into nps_unmatched (nps_name, nps_as_of, holding_level) values ($1, $2, $3) "
        "on conflict (nps_name, nps_as_of) do update set holding_level = excluded.holding_level",
        [(r["nps_name"], r["nps_as_of"], r["holding_level"]) for r in rows],
    )
    return len(rows)


async def fetch_resolved_unmatched(
    conn: Any, *, country_code: str = DEFAULT_COUNTRY
) -> list[dict]:
    """관리자가 resolved_ticker 를 채운 미해소 행을 reconcile 대상으로 조회.

    반환: [{nps_name, nps_as_of, holding_level, resolved_ticker}]. country_code 는 stocks 와
    무관(nps_unmatched 는 KR 전용)하지만 시그니처 일관성 위해 받는다.
    """
    rows = await conn.fetch(
        "select nps_name, nps_as_of, holding_level, resolved_ticker from nps_unmatched "
        "where resolved_ticker is not null"
    )
    return [dict(r) for r in rows]


async def delete_nps_unmatched(conn: Any, keys: list[tuple]) -> int:
    """해소 완료한 (nps_name, nps_as_of) 행 삭제. keys 비면 no-op."""
    if not keys:
        return 0
    await conn.executemany(
        "delete from nps_unmatched where nps_name = $1 and nps_as_of = $2", keys
    )
    return len(keys)
