"""종목 마스터(stocks/stock_aliases) 다중 소스 순차 병합 적재 — 주기 실행 진입점.

사용법:
    cd be
    poetry run python scripts/seed_stocks.py

병합 모델(소스 우선순위 순):
  1. 첫 소스(authority)  : 전 종목 UPSERT — 종목명을 canonical 로 확립.
  2. 다음 소스들          : 신규 ticker 는 추가, 기존 ticker 인데 이름이 다르면 그 이름을 별칭으로 등록.
  3. soft-delete         : 어떤 소스에도 없는 종목만 is_active=false (하드 삭제 안 함).
  4. 수동 약칭             : 대형주 구어체 약칭(현대차/삼전 등) 직접 등록.
  5. 종목별 Naver 교차검증 : 미검증 종목을 코드로 Naver 조회 — 이름 변형→별칭, 시장(typeCode) 교차검증.
                           naver_checked_at 으로 종목당 1회만(신규만 재질의). 병렬 처리(rate-limit 가드).

효율화(변경이 드문 데이터):
  - 소스별 내용 fingerprint(seed_source_state) 비교 → 무변경 소스는 UPSERT/별칭 skip(fetch+해시만).
  - 아무 소스도 안 바뀌면 soft-delete 도 skip.
  - Naver 교차검증은 naver_checked_at 으로 종목당 1회만(신규 종목만 추가 질의).

현재 소스: data.go.kr(공공데이터, authority, 키 필요) → FDR(FinanceDataReader, 키 불필요).
data.go.kr 인증 불가/미설정 시 FDR 만으로 동작(FDR 가 canonical 확립).
"""

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import asyncpg

# pyproject.toml 이 package-mode=false 라 invest_note_api 가 site-packages 에 없다.
_API_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

import httpx  # noqa: E402

from invest_note_api.config import Settings  # noqa: E402
from invest_note_api.domain.hangul import to_chosung  # noqa: E402
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY  # noqa: E402
from invest_note_api.external.constants import USER_AGENT  # noqa: E402
from invest_note_api.external.naver_search import search_kr  # noqa: E402

_DATA_GO_KR_URL = (
    "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"
)
_PAGE_SIZE = 1000
_NAVER_CONCURRENCY = 8          # Naver 자동완성 동시 호출 상한(rate-limit 가드)
_NAVER_STOCK_BATCH = 1500       # 종목별 교차검증 1회 run 당 처리 상한(첫 전수 검증은 여러 run 분산)


# ─────────────────────────── 종목 UPSERT (authority=overwrite / 하위=preserve) ───────────────────────────

# 첫 소스(authority): 종목명/시장/초성/출처를 덮어써 canonical 로 만든다.
_UPSERT_OVERWRITE_SQL = """
insert into stocks
    (country_code, ticker, asset_name, name_chosung, market, exchange, currency, source, is_active, updated_at)
values ($1, $2, $3, $4, $5, $6, $7, $8, true, now())
on conflict (country_code, ticker) do update set
    asset_name   = excluded.asset_name,
    name_chosung = excluded.name_chosung,
    market       = excluded.market,
    source       = excluded.source,
    is_active    = true,
    updated_at   = now()
"""

# 하위 소스: 기존 canonical(종목명·출처)을 보존하고 생존만 갱신. 신규 ticker 는 insert 로 이름·출처가 들어간다.
_UPSERT_PRESERVE_SQL = """
insert into stocks
    (country_code, ticker, asset_name, name_chosung, market, exchange, currency, source, is_active, updated_at)
values ($1, $2, $3, $4, $5, $6, $7, $8, true, now())
on conflict (country_code, ticker) do update set
    is_active  = true,
    updated_at = now()
"""


async def upsert_stocks(
    conn: Any,
    rows: list[dict],
    *,
    overwrite_name: bool,
    source: str,
    country_code: str = DEFAULT_COUNTRY,
) -> int:
    """종목 rows UPSERT. name_chosung 계산. `overwrite_name` 이면 종목명·출처 덮어쓰기(authority).

    `source` 는 이 소스의 식별자('data_go_kr'|'fdr'|...) — canonical 소유 소스로 기록.
    rows item: {ticker, asset_name, market, exchange?, currency?}
    """
    tuples = [
        (
            country_code,
            r["ticker"],
            r["asset_name"],
            to_chosung(r["asset_name"]),
            r["market"],
            r.get("exchange") or "KRX",
            r.get("currency") or "KRW",
            source,
        )
        for r in rows
        if r.get("ticker") and r.get("asset_name")
    ]
    if not tuples:
        return 0
    sql = _UPSERT_OVERWRITE_SQL if overwrite_name else _UPSERT_PRESERVE_SQL
    await conn.executemany(sql, tuples)
    return len(tuples)


async def soft_delete_not_in(conn: Any, country_code: str, tickers: set[str]) -> int:
    """현재 어떤 소스에도 없는 종목을 상폐 처리(is_active=false). 하드 삭제 안 함.

    `tickers` 는 이번 run 의 전 소스 union. fingerprint skip 과 무관하게 동작(updated_at 미사용).
    """
    result = await conn.execute(
        """
        update stocks set is_active = false, updated_at = now()
        where country_code = $1 and is_active and not (ticker = any($2::text[]))
        """,
        country_code,
        list(tickers),
    )
    return int(result.split()[-1]) if result.startswith("UPDATE") else 0


# ─────────────────────────── 별칭 UPSERT + 교차소스 변형명 ───────────────────────────

_UPSERT_ALIAS_SQL = """
insert into stock_aliases (country_code, ticker, alias, alias_chosung, source)
values ($1, $2, $3, $4, $5)
on conflict (country_code, ticker, alias) do update set
    alias_chosung = excluded.alias_chosung
"""


async def upsert_aliases(
    conn: Any, aliases: list[dict], *, country_code: str = DEFAULT_COUNTRY
) -> int:
    """alias rows 멱등 UPSERT. alias_chosung 계산. stocks 에 존재하는 ticker 만(FK)."""
    tuples = [
        (country_code, a["ticker"], a["alias"], to_chosung(a["alias"]), a.get("source", "manual"))
        for a in aliases
        if a.get("ticker") and a.get("alias")
    ]
    if not tuples:
        return 0
    existing = await _existing_tickers(conn, country_code, {t[1] for t in tuples})
    tuples = [t for t in tuples if t[1] in existing]
    if not tuples:
        return 0
    await conn.executemany(_UPSERT_ALIAS_SQL, tuples)
    return len(tuples)


async def _existing_tickers(conn: Any, country_code: str, tickers: set[str]) -> set[str]:
    rows = await conn.fetch(
        "select ticker from stocks where country_code = $1 and ticker = any($2::text[])",
        country_code,
        list(tickers),
    )
    return {r["ticker"] for r in rows}


async def variant_aliases(
    conn: Any, rows: list[dict], source: str, *, country_code: str = DEFAULT_COUNTRY
) -> list[dict]:
    """소스 rows 의 종목명이 DB 의 canonical 종목명과 다르면 그 변형명을 alias 로.

    upsert_stocks 후 호출 — DB 의 현재 asset_name(=먼저 등록한 소스의 canonical)과 비교한다.
    """
    tickers = [r["ticker"] for r in rows if r.get("ticker")]
    if not tickers:
        return []
    db = await conn.fetch(
        "select ticker, asset_name from stocks where country_code = $1 and ticker = any($2::text[])",
        country_code,
        tickers,
    )
    canon = {r["ticker"]: r["asset_name"] for r in db}
    return [
        {"ticker": r["ticker"], "alias": r["asset_name"], "source": source}
        for r in rows
        if (name := r.get("asset_name")) and canon.get(r["ticker"]) and name != canon[r["ticker"]]
    ]


# ─────────────────────────── fingerprint(무변경 skip) ───────────────────────────


def fingerprint(rows: list[dict]) -> str:
    """소스 내용의 정렬 안정 해시 — (ticker|name|market) 정렬 후 sha256."""
    items = sorted(f"{r['ticker']}|{r['asset_name']}|{r.get('market', '')}" for r in rows if r.get("ticker"))
    return hashlib.sha256("\n".join(items).encode()).hexdigest()


async def get_source_fingerprint(conn: Any, source: str) -> str | None:
    return await conn.fetchval(
        "select fingerprint from seed_source_state where source = $1", source
    )


async def set_source_fingerprint(conn: Any, source: str, fp: str, row_count: int) -> None:
    await conn.execute(
        """
        insert into seed_source_state (source, fingerprint, row_count, updated_at)
        values ($1, $2, $3, now())
        on conflict (source) do update set
            fingerprint = excluded.fingerprint,
            row_count   = excluded.row_count,
            updated_at  = now()
        """,
        source,
        fp,
        row_count,
    )


# ─────────────────────────── 소스 fetcher ───────────────────────────


async def fetch_data_go_kr(api_key: str) -> list[dict]:
    """공공데이터포털 금융위 KRX상장종목정보 — coverage(전 종목) 조회.

    ⚠️ 첫 실행 검증(스파이크): 응답 필드명(srtnCd/itmsNm/mrktCtg)·ETF/ETN 포함 여부를 실제 키로 확인.
    """
    rows: list[dict] = []
    page = 1
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        while True:
            res = await client.get(
                _DATA_GO_KR_URL,
                params={
                    "serviceKey": api_key,
                    "resultType": "json",
                    "numOfRows": _PAGE_SIZE,
                    "pageNo": page,
                },
            )
            res.raise_for_status()
            items = (
                res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
            )
            if not items:
                break
            for it in items:
                ticker = (it.get("srtnCd") or "").strip().lstrip("A")[-6:]
                name = (it.get("itmsNm") or "").strip()
                market = (it.get("mrktCtg") or "").strip()
                if ticker and name:
                    rows.append({"ticker": ticker, "asset_name": name, "market": market})
            if len(items) < _PAGE_SIZE:
                break
            page += 1
    return rows


# KOSDAQ 세부 구분(GLOBAL 등)은 표준 보드로 정규화 — 응답 exchange 가 trades.exchange 로 저장됨.
_FDR_MARKET_MAP = {"KOSDAQ GLOBAL": "KOSDAQ"}


def fetch_finance_data_reader() -> list[dict]:
    """FinanceDataReader 로 KR 전 종목(주식+ETF) coverage 조회 — API 키 불필요.

    동기 라이브러리라 batch 스크립트에서 직접 호출. 반환 shape: {ticker, asset_name, market}.
    ETN 은 FDR 미지원(graceful skip) — 후속에서 별도 소스 보강.
    """
    import FinanceDataReader as fdr  # seed 그룹 전용 — 지연 import

    rows: list[dict] = []

    krx = fdr.StockListing("KRX")
    for r in krx.itertuples(index=False):
        code = (getattr(r, "Code", "") or "").strip()
        name = (getattr(r, "Name", "") or "").strip()
        market = (getattr(r, "Market", "") or "").strip()
        if code and name:
            rows.append({"ticker": code, "asset_name": name, "market": _FDR_MARKET_MAP.get(market, market)})

    for listing, market in (("ETF/KR", "ETF"), ("ETN/KR", "ETN")):
        try:
            df = fdr.StockListing(listing)
        except Exception as e:
            print(f"  [fdr] {listing} 조회 건너뜀: {e}")
            continue
        col = "Symbol" if "Symbol" in df.columns else "Code"
        for r in df.itertuples(index=False):
            code = (getattr(r, col, "") or "").strip()
            name = (getattr(r, "Name", "") or "").strip()
            if code and name:
                rows.append({"ticker": code, "asset_name": name, "market": market})

    return rows


# ─────────────────────────── Naver enrichment(신규 miss 만) ───────────────────────────


async def crossvalidate_stocks_with_naver(
    conn: Any, *, country_code: str = DEFAULT_COUNTRY, batch: int = _NAVER_STOCK_BATCH
) -> tuple[int, int, int]:
    """종목별 Naver 교차검증 — 미검증(naver_checked_at IS NULL) 종목을 코드로 Naver 조회.

    - 이름 변형: Naver 종목명이 canonical 과 다르면 별칭(source='naver') 등록.
    - 시장 교차검증: Naver typeCode 가 stocks.market 과 다르면 불일치로 집계(자동 수정 안 함).
    - Naver 응답에서 해당 코드를 찾은 종목만 naver_checked_at 기록(미응답/rate-limit 은 다음 run 재시도).

    반환: (별칭 적재수, 시장 불일치수, 검증 완료 종목수).
    """
    rows = await conn.fetch(
        """
        select ticker, asset_name, market from stocks
        where country_code = $1 and is_active and naver_checked_at is null
        order by ticker limit $2
        """,
        country_code,
        batch,
    )
    if not rows:
        return (0, 0, 0)

    sem = asyncio.Semaphore(_NAVER_CONCURRENCY)
    aliases: list[dict] = []
    mismatches: list[tuple[str, str, str]] = []
    checked: list[str] = []

    async with httpx.AsyncClient(timeout=10) as client:

        async def _one(ticker: str, name: str, market: str) -> None:
            async with sem:
                results = await search_kr(ticker, client=client)
            match = next((r for r in results if r["code"] == ticker), None)
            if match is None:
                return  # 미응답/미발견 → 미체크(다음 run 재시도)
            checked.append(ticker)
            if match["name"] and match["name"] != name:
                aliases.append({"ticker": ticker, "alias": match["name"], "source": "naver"})
            if match["exchange"] and market and match["exchange"] != market:
                mismatches.append((ticker, market, match["exchange"]))

        await asyncio.gather(
            *(_one(r["ticker"], r["asset_name"], r["market"]) for r in rows)
        )

    n = await upsert_aliases(conn, aliases, country_code=country_code)
    if checked:
        await conn.execute(
            "update stocks set naver_checked_at = now() where country_code = $1 and ticker = any($2::text[])",
            country_code,
            checked,
        )
    if mismatches:
        sample = ", ".join(f"{t}:{m}≠{nv}" for t, m, nv in mismatches[:5])
        print(f"  [naver/market] 불일치 {len(mismatches)}건 (예: {sample})")
    return (n, len(mismatches), len(checked))


# ─────────────────────────── 오케스트레이션 ───────────────────────────


# 부트스트랩 약칭 시드(구어체). 대형주 구어체 약칭을 직접 등록.
_MANUAL_ALIASES = [
    {"ticker": "005380", "alias": "현대차", "source": "manual"},
    {"ticker": "005930", "alias": "삼전", "source": "manual"},
    {"ticker": "000660", "alias": "하이닉스", "source": "manual"},
    {"ticker": "035420", "alias": "네이버", "source": "manual"},
    {"ticker": "035720", "alias": "카카오", "source": "manual"},
]


def _build_pipeline(api_key: str) -> list[tuple[str, Callable[[], Awaitable[list[dict]]]]]:
    """소스 우선순위 파이프라인. 첫 소스가 canonical authority. 실패 소스는 [] 반환."""

    async def _dgk() -> list[dict]:
        if not api_key:
            return []
        try:
            return await fetch_data_go_kr(api_key)
        except Exception as e:
            # serviceKey 가 URL 에 포함돼 예외 메시지로 새지 않도록 상태코드만 노출.
            status = getattr(getattr(e, "response", None), "status_code", None)
            print(f"  [data_go_kr] 실패({f'HTTP {status}' if status else type(e).__name__}) — skip")
            return []

    async def _fdr() -> list[dict]:
        return fetch_finance_data_reader()

    return [("data_go_kr", _dgk), ("fdr", _fdr)]


async def seed(db_url: str, *, api_key: str) -> None:
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        # fingerprint skip 은 "seed_source_state 가 stocks 내용을 반영한다"를 전제한다.
        # DB 가 out-of-band 로 비워지면(db reset/수동 wipe) stale fingerprint 가 재적재를 막으므로,
        # stocks 가 비어있으면 state 를 무효화해 전체 재적재를 강제한다.
        if await conn.fetchval("select count(*) from stocks") == 0:
            await conn.execute("delete from seed_source_state")

        union: set[str] = set()
        any_changed = False
        authority_used = False   # 첫 번째로 데이터를 반환한 소스 = canonical authority(overwrite)
        upstream_changed = False  # 앞선 소스가 바뀌면 canonical 이 이동했을 수 있어 하위 변형명 재계산 필요

        # 1~2) 소스 순차 병합 (authority=이름 확립, 이후=신규 추가 + 변형명 별칭)
        for name, fetch in _build_pipeline(api_key):
            rows = await fetch()
            if not rows:
                continue
            union.update(r["ticker"] for r in rows if r.get("ticker"))
            is_authority = not authority_used
            authority_used = True

            fp = fingerprint(rows)
            unchanged = fp == await get_source_fingerprint(conn, name)

            if unchanged and not upstream_changed:
                print(f"  [{name}] 변경 없음 — skip ({len(rows)}건)")
                continue

            if unchanged:
                # 소스 자체는 그대로지만 앞선 소스로 canonical 이 바뀜 → 변형명 별칭만 재계산.
                va = await upsert_aliases(conn, await variant_aliases(conn, rows, name))
                print(f"  [{name}] canonical 변동 → 변형 별칭 {va}건 재계산")
                continue

            n = await upsert_stocks(conn, rows, overwrite_name=is_authority, source=name)
            va = await upsert_aliases(conn, await variant_aliases(conn, rows, name))
            await set_source_fingerprint(conn, name, fp, n)
            any_changed = True
            upstream_changed = True
            print(f"  [{name}] {n}건 반영, 변형 별칭 {va}건" + (" (authority)" if is_authority else ""))

        # 3) soft-delete — 변경이 있었을 때만(어떤 소스에도 없는 종목 비활성화)
        if any_changed and union:
            print(f"  [soft-delete] {await soft_delete_not_in(conn, DEFAULT_COUNTRY, union)}건")
        elif not union:
            print("  [soft-delete] 유효 소스 없음 — skip")
        else:
            print("  [soft-delete] 변경 없음 — skip")

        # 4) 수동 약칭(멱등)
        print(f"  [alias/manual] {await upsert_aliases(conn, _MANUAL_ALIASES)}건")

        # 5) 종목별 Naver 교차검증(미검증 종목만, 종목당 1회) — 이름 변형 별칭 + 시장 교차검증
        na, mm, ck = await crossvalidate_stocks_with_naver(conn)
        print(f"  [naver/stock] 검증 {ck}건, 이름변형 별칭 {na}건, 시장불일치 {mm}건")

        print("완료.")
    finally:
        await conn.close()


def main() -> None:
    settings = Settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        raise SystemExit("database_url 미설정")
    asyncio.run(seed(db_url, api_key=settings.data_go_kr_api_key))


if __name__ == "__main__":
    main()
