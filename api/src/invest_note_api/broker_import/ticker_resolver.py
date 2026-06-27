"""종목명/ISIN → ticker 변환 (ISIN 우선, 종목명 폴백)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, TypedDict

from invest_note_api.db_ops import isin_cache_repo, stocks_repo
from invest_note_api.external.openfigi import OpenFigiResult, exch_code_to_country, map_isins

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
    isins: dict[ResolveKey, str] | None = None,
    openfigi_api_key: str | None = None,
) -> dict[ResolveKey, ResolvedTicker | None]:
    """(country_code, asset_name) → {code, exchange} 매핑.

    해소 우선순위:
    1. **ISIN 매칭**(있을 때) — OpenFIGI 로 ISIN→ticker 해소(캐시 우선). 성공 시 그 ticker 가
       권위. exchange 는 로컬 stocks 에 있으면 채우고 없으면 "". (ticker_hint 와 동일 사상)
    2. **종목명 매칭**(ISIN 없음/ISIN 미해결) — country-scoped `lookup_by_names`. US 섹션
       종목명이 KR alias 에 오매칭(예: 애플→PLUS 애플채권혼합)되는 것을 막는다.
    3. 미해결: None.

    - code: ticker_hints(파일에서 직접 추출한 코드)가 있으면 권위, 없으면 ISIN/로컬 검색.
    - exchange: 파일에 거래소 정보가 없어 항상 로컬 매칭에서 가져온다.

    `conn` 은 stocks/isin_ticker_map(public) 를 읽고 쓸 수 있는 connection(plain pool.acquire).
    `isins` 가 비어 있으면 OpenFIGI/캐시 경로를 아예 타지 않는다(conn=None 단위 테스트 호환).
    """
    isins = isins or {}

    # ── 1. ISIN 우선 해소 (isins 있을 때만 캐시/OpenFIGI 접근) ──
    isin_resolved: dict[ResolveKey, ResolvedTicker] = {}
    if isins:
        isin_resolved = await _resolve_by_isin(
            items, isins, conn=conn, api_key=openfigi_api_key
        )

    # ── 2. 나머지(ISIN 없음/ISIN 미해결) 종목명 매칭 폴백 ──
    name_items = {k for k in items if k not in isin_resolved}
    name_resolved = await _resolve_by_name(name_items, ticker_hints, conn=conn)

    result: dict[ResolveKey, ResolvedTicker | None] = {}
    result.update(name_resolved)
    result.update(isin_resolved)
    return result


async def _resolve_by_name(
    items: set[ResolveKey],
    ticker_hints: dict[ResolveKey, str],
    *,
    conn: Any,
) -> dict[ResolveKey, ResolvedTicker | None]:
    """종목명 country-scoped 매칭 (+ ticker_hint 권위). 기존 동작."""
    if not items:
        return {}

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


async def _resolve_by_isin(
    items: set[ResolveKey],
    isins: dict[ResolveKey, str],
    *,
    conn: Any,
    api_key: str | None,
) -> dict[ResolveKey, ResolvedTicker]:
    """ISIN 매칭: 캐시 조회 → 미스 OpenFIGI 배치 → 캐시 upsert → ticker 로 stocks exchange.

    반환에는 **해소 성공한 키만** 담는다(미해결 키는 빠져서 호출자가 종목명 폴백). ticker
    해소가 됐으면 stocks 매칭이 없어도(exchange="") 성공으로 친다 — ticker 가 권위.
    """
    # isin 이 실제로 있는 항목만
    keyed = {k: isins[k] for k in items if isins.get(k)}
    if not keyed:
        return {}

    unique_isins = list(dict.fromkeys(keyed.values()))

    # 1. 캐시 조회 (positive + negative 모두 hit 으로 간주 → OpenFIGI 재조회 방지)
    cached = await isin_cache_repo.fetch_cached(conn, unique_isins)

    # 2. 캐시 미스 ISIN → OpenFIGI 배치 해소
    miss = [i for i in unique_isins if i not in cached]
    fetched: dict[str, OpenFigiResult | None] = {}
    if miss:
        fetched = await map_isins(miss, api_key=api_key)
        # 3. 캐시 upsert (해소/미해결 모두 — negative cache)
        await isin_cache_repo.upsert(conn, _to_cache_rows(miss, fetched))

    # 4. isin → {ticker, country_code} (캐시 positive + 이번 fetch 성공분)
    resolved_by_isin: dict[str, dict[str, str]] = {}
    for isin in unique_isins:
        row = cached.get(isin)
        if row is not None and row["resolved"] and row["ticker"]:
            resolved_by_isin[isin] = {
                "ticker": row["ticker"],
                "country_code": row["country_code"] or exch_code_to_country(""),
            }
            continue
        figi = fetched.get(isin)
        if figi is not None:
            resolved_by_isin[isin] = {
                "ticker": figi["ticker"],
                "country_code": exch_code_to_country(figi["exch_code"]),
            }

    if not resolved_by_isin:
        return {}

    # 5. ticker → stocks 조회로 exchange 채움 (country-scoped)
    tickers_by_country: dict[str, set[str]] = defaultdict(set)
    for v in resolved_by_isin.values():
        tickers_by_country[v["country_code"]].add(v["ticker"])

    stock_matches: dict[tuple[str, str], dict] = {}
    for country_code, tickers in tickers_by_country.items():
        matched = await stocks_repo.lookup_by_tickers(
            conn, list(tickers), country_code=country_code
        )
        for ticker, match in matched.items():
            stock_matches[(country_code, ticker)] = match

    # 6. 키별 결과 (해소 성공만 — 미해결은 빠져서 종목명 폴백)
    out: dict[ResolveKey, ResolvedTicker] = {}
    for key, isin in keyed.items():
        r = resolved_by_isin.get(isin)
        if r is None:
            continue
        match = stock_matches.get((r["country_code"], r["ticker"].upper()))
        out[key] = {
            "code": r["ticker"],
            "exchange": match["exchange"] if match else "",
        }
    return out


def _to_cache_rows(
    isins: list[str], fetched: dict[str, OpenFigiResult | None]
) -> list[dict]:
    """OpenFIGI 결과 → isin_ticker_map upsert rows(해소/미해결 모두)."""
    rows: list[dict] = []
    for isin in isins:
        figi = fetched.get(isin)
        if figi is not None:
            rows.append(
                {
                    "isin": isin,
                    "ticker": figi["ticker"],
                    "exch_code": figi["exch_code"],
                    "country_code": exch_code_to_country(figi["exch_code"]),
                    "name": figi["name"],
                    "resolved": True,
                }
            )
        else:
            rows.append(
                {
                    "isin": isin,
                    "ticker": None,
                    "exch_code": None,
                    "country_code": None,
                    "name": None,
                    "resolved": False,
                }
            )
    return rows
