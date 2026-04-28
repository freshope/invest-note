"""종목명 → ticker 변환 (kr_stocks 테이블 lookup)."""

from __future__ import annotations

from asyncpg import Connection

from invest_note_api.db_ops.kr_stocks_repo import lookup_by_names


async def resolve_tickers(
    conn: Connection, asset_names: set[str], ticker_hints: dict[str, str]
) -> dict[str, str | None]:
    """asset_name → ticker 매핑을 반환한다.

    우선순위:
    1. ticker_hints (파일에서 직접 추출한 코드)
    2. kr_stocks 테이블 lookup
    3. None (미해결)
    """
    result: dict[str, str | None] = {}

    # ticker_hint 먼저 적용
    remaining = set()
    for name in asset_names:
        if name in ticker_hints:
            result[name] = ticker_hints[name]
        else:
            remaining.add(name)

    if remaining:
        db_map = await lookup_by_names(conn, list(remaining))
        for name in remaining:
            result[name] = db_map.get(name)

    return result
