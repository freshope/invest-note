"""어드민 패널 repo — 메인 풀(invest_note_app=owner) 기반 read + stocks/nps 쓰기.

RLS 제거 후 owner connection 이 user_id 필터 없이 cross-user 전 행을 조회한다. 테이블/컬럼명은
전부 이 모듈의 상수 화이트리스트에서만 오므로(사용자 입력 미주입) f-string SQL 조립이 안전하다.
값은 항상 $n 파라미터.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

# 리스트 가능한 테이블 → (실제 테이블명, q 부분일치 검색 컬럼들, 기본 정렬절).
# 선택 키: from(기본 table), select(기본 *) — JOIN 으로 다른 테이블 컬럼을 합쳐 노출할 때 사용.
# users 는 신원/프로필이 1:1 user_profiles 로 격리돼 있어 LEFT JOIN 으로 합쳐 노출한다.
_LIST_TABLES: dict[str, dict[str, Any]] = {
    "users": {
        "table": "users",
        "from": "users u left join user_profiles p on p.user_id = u.id",
        "select": (
            "u.id, u.created_at, p.email, p.display_name, p.avatar_url, "
            "p.email_verified, p.providers, p.last_sign_in"
        ),
        "search": ["u.id::text", "p.email", "p.display_name"],
        "order": "u.created_at desc",
    },
    "accounts": {"table": "accounts", "search": ["name"], "order": "created_at desc"},
    "trades": {
        "table": "trades",
        "search": ["ticker_symbol", "asset_name"],
        "order": "traded_at desc",
    },
    "custom_tags": {"table": "custom_tags", "search": ["label"], "order": "created_at desc"},
    "stocks": {
        "table": "stocks",
        "search": ["asset_name", "ticker"],
        "order": "country_code, ticker",
    },
    "nps_unmatched": {
        "table": "nps_unmatched",
        "search": ["nps_name"],
        "order": "created_at desc",
    },
    # 거래내역서 원장 배치(파일 1건=1행). 업로더 email·등록 계좌명은 LEFT JOIN, 행수는 서브쿼리.
    # entry_count=원장 전체 행, trade_row_count=거래 행(trade_type 有; 비거래/오류 행 제외).
    "import_batches": {
        "table": "import_batches",
        "from": (
            "import_batches b "
            "left join user_profiles p on p.user_id = b.user_id "
            "left join accounts a on a.id = b.account_id"
        ),
        "select": (
            "b.id, b.broker_key, b.filename, b.content_type, b.size_bytes, "
            "b.account_hint, b.account_id, a.name as account_name, "
            "b.committed_at, b.created_at, b.parsed_at, p.email, "
            "(select count(*) from import_ledger_entries e where e.batch_id = b.id) "
            "as entry_count, "
            "(select count(*) from import_ledger_entries e "
            "  where e.batch_id = b.id and e.trade_type is not null) as trade_row_count"
        ),
        "search": ["b.filename", "b.broker_key", "p.email"],
        "order": "b.created_at desc",
    },
}

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _escape_like(term: str) -> str:
    """ILIKE 패턴의 와일드카드를 이스케이프(기본 ESCAPE '\\')."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_rows(
    conn: Any,
    table_key: str,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    q: str | None = None,
) -> tuple[list[dict], int]:
    """공통 목록 조회 — (rows, total). table_key 는 _LIST_TABLES 화이트리스트에서만.

    page 1-base, page_size 는 [1, MAX_PAGE_SIZE] clamp. q 는 테이블별 대표 컬럼 부분일치(ILIKE).
    rows 는 snake_case dict(컬럼 그대로). total 은 검색 적용 후 전체 건수.
    """
    meta = _LIST_TABLES[table_key]  # KeyError 면 라우터가 사전에 검증(404)
    table = meta["table"]
    from_clause = meta.get("from", table)  # JOIN 등 — 기본은 단일 테이블
    select_cols = meta.get("select", "*")
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    offset = (page - 1) * page_size

    where = ""
    args: list[Any] = []
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        args.append(pattern)
        clauses = " or ".join(f"{col} ilike $1" for col in meta["search"])
        where = f"where {clauses}"

    total = await conn.fetchval(f"select count(*) from {from_clause} {where}", *args)

    args.extend([page_size, offset])
    rows = await conn.fetch(
        f"select {select_cols} from {from_clause} {where} order by {meta['order']} "
        f"limit ${len(args) - 1} offset ${len(args)}",
        *args,
    )
    return [dict(r) for r in rows], int(total or 0)


# 원장 배치 상세 — 목록과 동일한 조인/서브쿼리 + 원문 식별 컬럼(storage_key·sha256·parser_version).
_IMPORT_BATCH_DETAIL_SQL = """
SELECT b.id, b.user_id, b.broker_key, b.parser_version, b.filename,
       b.content_type, b.size_bytes, b.storage_key, b.content_sha256,
       b.account_hint, b.account_id, a.name AS account_name,
       b.committed_at, b.created_at, b.parsed_at, p.email,
       (SELECT count(*) FROM import_ledger_entries e WHERE e.batch_id = b.id)
           AS entry_count,
       (SELECT count(*) FROM import_ledger_entries e
         WHERE e.batch_id = b.id AND e.trade_type IS NOT NULL) AS trade_row_count
  FROM import_batches b
  LEFT JOIN user_profiles p ON p.user_id = b.user_id
  LEFT JOIN accounts a ON a.id = b.account_id
 WHERE b.id = $1
"""

# 배치의 원장 행 전량(append-only, source_row_no 순). raw 는 파싱 원문 전체(jsonb).
_LEDGER_ENTRIES_SQL = """
SELECT id, source_row_no, traded_at_raw, traded_at, trade_type,
       asset_name, ticker_hint, isin, country_code, quantity, price,
       commission, tax, exchange_rate, raw, created_at
  FROM import_ledger_entries
 WHERE batch_id = $1
 ORDER BY source_row_no
"""


async def get_import_batch(conn: Any, batch_id: UUID) -> dict | None:
    """원장 배치 상세(메타 + email·account_name·행수 조인). 없으면 None."""
    row = await conn.fetchrow(_IMPORT_BATCH_DETAIL_SQL, batch_id)
    return dict(row) if row is not None else None


async def list_ledger_entries(conn: Any, batch_id: UUID) -> list[dict]:
    """배치의 원장 행 전량. raw jsonb 는 asyncpg 가 str 로 주므로 dict 로 디코드(board_repo 관례)."""
    rows = await conn.fetch(_LEDGER_ENTRIES_SQL, batch_id)
    result: list[dict] = []
    for r in rows:
        d = dict(r)
        raw = d.get("raw")
        if isinstance(raw, str):
            d["raw"] = json.loads(raw)
        result.append(d)
    return result


async def get_stats(conn: Any) -> dict[str, int]:
    """대시보드 카운트 — 단일 쿼리로 테이블 건수. admin pool 이라 cross-user 전수."""
    row = await conn.fetchrow(
        """
        select
            (select count(*) from users) as users,
            (select count(*) from accounts) as accounts,
            (select count(*) from trades) as trades,
            (select count(*) from stocks) as stocks,
            (select count(*) from nps_unmatched) as nps_unmatched,
            (select count(*) from board_posts where board_type = 'broker_statement') as broker_statements
        """
    )
    return {
        k: int(row[k])
        for k in ("users", "accounts", "trades", "stocks", "nps_unmatched", "broker_statements")
    }


async def get_user_growth(conn: Any) -> list[dict[str, Any]]:
    """일별 가입자 시계열 — [{date, cumulative, new_users}], 가입일 오름차순.

    created_at 을 KST(Asia/Seoul)로 변환해 날짜 버킷팅한다(단순 ::date 는 UTC 버킷이라
    KST 가입일이 ±9h 어긋남). 첫 가입일~오늘(KST)까지 generate_series 로 연속 날짜를
    만들어 가입 없는 날도 0 으로 채운다 — 시계열 차트에 빈 날짜도 표시되도록.
    """
    rows = await conn.fetch(
        """
        with daily as (
            select
                (created_at at time zone 'Asia/Seoul')::date as day,
                count(*) as cnt
            from users
            group by day
        ),
        series as (
            select generate_series(
                (select min(day) from daily),
                (now() at time zone 'Asia/Seoul')::date,
                interval '1 day'
            )::date as day
        )
        select
            s.day as date,
            coalesce(d.cnt, 0) as new_users,
            sum(coalesce(d.cnt, 0)) over (order by s.day) as cumulative
        from series s
        left join daily d on d.day = s.day
        order by s.day
        """
    )
    return [
        {"date": r["date"], "cumulative": int(r["cumulative"]), "new_users": int(r["new_users"])}
        for r in rows
    ]


async def get_deletion_stats(conn: Any) -> dict[str, Any]:
    """회원 탈퇴 통계 — 요약 카운트 + 일별 추이 + 사유 분포.

    추이는 get_user_growth 와 동일하게 KST 버킷 + generate_series 로 빈 날 0 채움.
    탈퇴가 0 건이면 min(day) 가 NULL → generate_series 가 0 행 → trend=[](안전).
    avg_lifetime_days 는 signup_at 이 있는 행만(현재는 항상 채워지나 방어).
    """
    summary = await conn.fetchrow(
        """
        select
            (select count(*) from users) as total_users,
            (select count(*) from account_deletions) as total_deletions,
            (select count(*) from account_deletions
                where deleted_at >= now() - interval '30 days') as deletions_30d,
            (select avg(extract(epoch from (deleted_at - signup_at)) / 86400.0)
                from account_deletions where signup_at is not null) as avg_lifetime_days
        """
    )
    total_users = int(summary["total_users"])
    total_deletions = int(summary["total_deletions"])
    ever = total_users + total_deletions
    churn_rate = (total_deletions / ever) if ever else 0.0
    avg_lifetime = summary["avg_lifetime_days"]

    trend = await conn.fetch(
        """
        with daily as (
            select (deleted_at at time zone 'Asia/Seoul')::date as day, count(*) as cnt
            from account_deletions
            group by day
        ),
        series as (
            select generate_series(
                (select min(day) from daily),
                (now() at time zone 'Asia/Seoul')::date,
                interval '1 day'
            )::date as day
        )
        select s.day as date, coalesce(d.cnt, 0) as deletions
        from series s
        left join daily d on d.day = s.day
        order by s.day
        """
    )
    reasons = await conn.fetch(
        """
        select coalesce(reason, 'unspecified') as reason, count(*) as count
        from account_deletions
        group by coalesce(reason, 'unspecified')
        order by count desc, reason
        """
    )
    return {
        "total_users": total_users,
        "total_deletions": total_deletions,
        "churn_rate": round(float(churn_rate), 4),
        "deletions_30d": int(summary["deletions_30d"]),
        "avg_lifetime_days": (
            round(float(avg_lifetime), 1) if avg_lifetime is not None else None
        ),
        "trend": [{"date": r["date"], "deletions": int(r["deletions"])} for r in trend],
        "reasons": [{"reason": r["reason"], "count": int(r["count"])} for r in reasons],
    }


# ─────────────────────────── stocks 수정 (PK = country_code, ticker) ───────────────────────────

# StockUpdate 화이트리스트와 1:1. seed 가 덮어쓰지 않는 필드만(스키마 docstring 참조).
_STOCK_EDITABLE = ("asset_name", "market", "exchange", "sector", "currency", "is_active", "us_index")


async def update_stock(
    conn: Any, country_code: str, ticker: str, fields: dict[str, Any]
) -> dict | None:
    """stocks 부분 수정. fields 는 StockUpdate 화이트리스트 통과분(전달된 키만).

    빈 fields 면 갱신 없이 현재 행 반환. 없는 행이면 None(라우터가 404). updated_at 갱신.
    """
    edits = {k: v for k, v in fields.items() if k in _STOCK_EDITABLE}
    if not edits:
        row = await conn.fetchrow(
            "select * from stocks where country_code = $1 and ticker = $2",
            country_code,
            ticker,
        )
        return dict(row) if row else None

    cols = list(edits)
    set_clause = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(cols))
    values = [edits[c] for c in cols]
    values.extend([country_code, ticker])
    row = await conn.fetchrow(
        f"update stocks set {set_clause}, updated_at = now() "
        f"where country_code = ${len(cols) + 1} and ticker = ${len(cols) + 2} returning *",
        *values,
    )
    return dict(row) if row else None


# ─────────────────────────── nps_unmatched CRUD (PK = nps_name, nps_as_of) ───────────────────────────


async def create_nps_unmatched(
    conn: Any,
    *,
    nps_name: str,
    nps_as_of: date,
    holding_level: str,
    resolved_ticker: str | None = None,
) -> dict | None:
    """nps_unmatched 생성. PK 충돌(이미 존재) 시 None(라우터가 409)."""
    row = await conn.fetchrow(
        "insert into nps_unmatched (nps_name, nps_as_of, holding_level, resolved_ticker) "
        "values ($1, $2, $3, $4) on conflict (nps_name, nps_as_of) do nothing returning *",
        nps_name,
        nps_as_of,
        holding_level,
        resolved_ticker,
    )
    return dict(row) if row else None


async def update_nps_unmatched(
    conn: Any, *, nps_name: str, nps_as_of: date, fields: dict[str, Any]
) -> dict | None:
    """nps_unmatched 부분 수정(resolved_ticker/holding_level). 없는 행이면 None(404).

    빈 fields 면 현재 행 반환. PK(nps_name, nps_as_of)는 식별자라 수정 대상 아님.
    """
    allowed = ("holding_level", "resolved_ticker")
    edits = {k: v for k, v in fields.items() if k in allowed}
    if not edits:
        row = await conn.fetchrow(
            "select * from nps_unmatched where nps_name = $1 and nps_as_of = $2",
            nps_name,
            nps_as_of,
        )
        return dict(row) if row else None

    cols = list(edits)
    set_clause = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(cols))
    values = [edits[c] for c in cols]
    values.extend([nps_name, nps_as_of])
    row = await conn.fetchrow(
        f"update nps_unmatched set {set_clause} "
        f"where nps_name = ${len(cols) + 1} and nps_as_of = ${len(cols) + 2} returning *",
        *values,
    )
    return dict(row) if row else None


async def delete_nps_unmatched_row(conn: Any, *, nps_name: str, nps_as_of: date) -> bool:
    """nps_unmatched 1행 삭제. 삭제 성공 True, 없는 행 False(라우터가 404)."""
    result = await conn.execute(
        "delete from nps_unmatched where nps_name = $1 and nps_as_of = $2",
        nps_name,
        nps_as_of,
    )
    return result.endswith(" 1")
