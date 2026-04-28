"""종목명 → ticker 변환 (stocks 마스터 테이블 lookup)."""

from __future__ import annotations

from asyncpg import Connection

from invest_note_api.db_ops.stocks_repo import lookup_by_names
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY


async def resolve_tickers(
    conn: Connection,
    asset_names: set[str],
    ticker_hints: dict[str, str],
    country_code: str = DEFAULT_COUNTRY,
) -> dict[str, str | None]:
    """asset_name → ticker 매핑을 반환한다.

    우선순위:
    1. ticker_hints (파일에서 직접 추출한 코드)
    2. stocks 테이블 lookup (country_code 범위)
    3. None (미해결)
    """
    result: dict[str, str | None] = {}

    remaining = set()
    for name in asset_names:
        if name in ticker_hints:
            result[name] = ticker_hints[name]
        else:
            remaining.add(name)

    if remaining:
        db_map = await lookup_by_names(conn, list(remaining), country_code=country_code)
        for name in remaining:
            result[name] = db_map.get(name)

    return result
