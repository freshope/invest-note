"""어드민 패널 repo — admin pool(invest_note_admin BYPASSRLS) 기반 read + stocks/nps 쓰기.

acquire_admin 으로 받은 plain connection 을 쓴다(GUC 미주입). FORCE RLS 테이블도 BYPASSRLS
역할이라 cross-user 무필터 조회된다. 테이블/컬럼명은 전부 이 모듈의 상수 화이트리스트에서만
오므로(사용자 입력 미주입) f-string SQL 조립이 안전하다. 값은 항상 $n 파라미터.
"""
from __future__ import annotations

from datetime import date
from typing import Any

# 리스트 가능한 테이블 → (실제 테이블명, q 부분일치 검색 컬럼들, 기본 정렬절).
# q 컬럼은 row shape 기준으로 확정: users 는 email 컬럼이 없어 id 텍스트로 매칭한다.
_LIST_TABLES: dict[str, dict[str, Any]] = {
    "users": {"table": "users", "search": ["id::text"], "order": "created_at desc"},
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
}

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _escape_like(term: str) -> str:
    """ILIKE 패턴의 와일드카드를 이스케이프(기본 ESCAPE '\\')."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_table_names() -> list[str]:
    return list(_LIST_TABLES)


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

    total = await conn.fetchval(f"select count(*) from {table} {where}", *args)

    args.extend([page_size, offset])
    rows = await conn.fetch(
        f"select * from {table} {where} order by {meta['order']} "
        f"limit ${len(args) - 1} offset ${len(args)}",
        *args,
    )
    return [dict(r) for r in rows], int(total or 0)


async def get_stats(conn: Any) -> dict[str, int]:
    """대시보드 카운트 — 단일 쿼리로 5개 테이블 건수. admin pool 이라 cross-user 전수."""
    row = await conn.fetchrow(
        """
        select
            (select count(*) from users) as users,
            (select count(*) from accounts) as accounts,
            (select count(*) from trades) as trades,
            (select count(*) from stocks) as stocks,
            (select count(*) from nps_unmatched) as nps_unmatched
        """
    )
    return {k: int(row[k]) for k in ("users", "accounts", "trades", "stocks", "nps_unmatched")}


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
