"""종목명 → ticker 변환 (로컬 stocks 마스터)."""

from __future__ import annotations

from typing import Any, TypedDict

from invest_note_api.db_ops import stocks_repo


class ResolvedTicker(TypedDict):
    code: str
    exchange: str


async def resolve_tickers(
    asset_names: set[str],
    ticker_hints: dict[str, str],
    *,
    conn: Any,
) -> dict[str, ResolvedTicker | None]:
    """asset_name → {code, exchange} 매핑.

    - code: ticker_hints(파일에서 직접 추출한 코드)가 있으면 그것을 권위로 사용,
      없으면 로컬 stocks 검색 1순위 매칭.
    - exchange: 파일에는 거래소 정보가 없으므로 항상 로컬 매칭에서 가져온다.
      hint 가 있어 code 는 확정이어도 exchange 채움을 위해 매칭을 조회한다.
    - 미해결(코드 없음): None.

    `conn` 은 stocks(public, RLS 미적용) 를 읽을 수 있는 connection (plain pool.acquire 가능).
    """
    names = list(asset_names)
    matches = await stocks_repo.lookup_by_names(conn, names)

    result: dict[str, ResolvedTicker | None] = {}
    for name in names:
        match = matches.get(name)
        hint = ticker_hints.get(name)
        if hint is not None:
            result[name] = {
                "code": hint,
                "exchange": match["exchange"] if match else "",
            }
        elif match is not None:
            result[name] = {"code": match["code"], "exchange": match["exchange"]}
        else:
            result[name] = None

    return result
