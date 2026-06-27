"""종목명 → ticker 변환 (로컬 stocks 마스터)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, TypedDict

from invest_note_api.db_ops import stocks_repo

# (country_code, asset_name) — 같은 종목명이 KR/US 양쪽에 존재할 수 있어 국가를 키에 포함한다.
ResolveKey = tuple[str, str]


class ResolvedTicker(TypedDict):
    code: str
    exchange: str


async def resolve_tickers(
    items: set[ResolveKey],
    ticker_hints: dict[ResolveKey, str],
    *,
    conn: Any,
) -> dict[ResolveKey, ResolvedTicker | None]:
    """(country_code, asset_name) → {code, exchange} 매핑.

    - 매칭은 **거래 country 로 스코프**한다. `lookup_by_names` 를 country 별로 호출해
      US 섹션 종목명이 KR 스코프 alias 에 오매칭(예: 애플→PLUS 애플채권혼합)되는 것을 막는다.
    - code: ticker_hints(파일에서 직접 추출한 코드)가 있으면 그것을 권위로 사용,
      없으면 로컬 stocks 검색 1순위 매칭.
    - exchange: 파일에는 거래소 정보가 없으므로 항상 로컬 매칭에서 가져온다.
      hint 가 있어 code 는 확정이어도 exchange 채움을 위해 매칭을 조회한다.
    - 미해결(코드 없음): None.

    `conn` 은 stocks(public, RLS 미적용) 를 읽을 수 있는 connection (plain pool.acquire 가능).
    """
    # country 별로 종목명을 그룹핑 → country-scoped lookup
    names_by_country: dict[str, list[str]] = defaultdict(list)
    for country_code, name in items:
        names_by_country[country_code].append(name)

    matches_by_country: dict[str, dict[str, Any]] = {}
    for country_code, names in names_by_country.items():
        matches_by_country[country_code] = await stocks_repo.lookup_by_names(
            conn, names, country_code=country_code
        )

    result: dict[ResolveKey, ResolvedTicker | None] = {}
    for country_code, name in items:
        match = matches_by_country[country_code].get(name)
        hint = ticker_hints.get((country_code, name))
        if hint is not None:
            result[(country_code, name)] = {
                "code": hint,
                "exchange": match["exchange"] if match else "",
            }
        elif match is not None:
            result[(country_code, name)] = {
                "code": match["code"],
                "exchange": match["exchange"],
            }
        else:
            result[(country_code, name)] = None

    return result
