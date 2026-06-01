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
  6. marcap 적재          : 주식시세·증권상품시세에서 시가총액을 UPDATE — fingerprint skip 우회(always-run).

효율화(변경이 드문 데이터):
  - 소스별 내용 fingerprint(seed_source_state) 비교 → 무변경 소스는 UPSERT/별칭 skip(fetch+해시만).
  - 아무 소스도 안 바뀌면 soft-delete 도 skip.
  - Naver 교차검증은 naver_checked_at 으로 종목당 1회만(신규 종목만 추가 질의).
  - 단, marcap 은 매일 변동하므로 fingerprint 와 무관하게 항상 갱신.

현재 소스: data.go.kr(공공데이터, 키 필요) — KRX상장종목정보(주식 authority) + 증권상품시세(ETF/ETN coverage)
+ 주식/증권상품시세 marcap. FDR 폐기.
"""

import asyncio
import hashlib
from datetime import date, timedelta
from typing import Any, Awaitable, Callable

import asyncpg
import httpx

from invest_note_api.config import Settings
from invest_note_api.domain.hangul import to_chosung
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY
from invest_note_api.external.constants import USER_AGENT
from invest_note_api.external.naver_search import search_kr

_DATA_GO_KR_URL = (
    "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"
)
# 증권상품시세(15094806) — ETF/ETN 시세·시총.
_SECURITIES_PRODUCT_BASE = (
    "https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService"
)
# 주식시세(15094808) — 주식 시총.
_STOCK_PRICE_URL = (
    "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
)
_PAGE_SIZE = 1000
_NAVER_CONCURRENCY = 8          # Naver 자동완성 동시 호출 상한(rate-limit 가드)
_NAVER_STOCK_BATCH = 1500       # 종목별 교차검증 1회 run 당 처리 상한(첫 전수 검증은 여러 run 분산)
_BASDT_MAX_LOOKBACK = 7         # basDt 직전 영업일 fallback 최대 거슬러 일수(주말/휴장 대응)


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

    `source` 는 이 소스의 식별자('data_go_kr'|...) — canonical 소유 소스로 기록.
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


# ─────────────────────────── 시가총액 fetcher (data.go.kr 시세) ───────────────────────────


def _recent_basdt_candidates() -> list[str]:
    """직전 영업일부터 거슬러 시도할 basDt(YYYYMMDD) 후보 리스트.

    FSC 시세 API 는 영업일 T+1(~13:00 KST) 발행이라 당일/미발행일은 빈 응답이다.
    주말·휴장은 별도 캘린더 없이 "빈 응답이면 하루 더 거슬러"로 처리한다(최대 _BASDT_MAX_LOOKBACK 일).
    """
    today = date.today()
    return [(today - timedelta(days=d)).strftime("%Y%m%d") for d in range(1, _BASDT_MAX_LOOKBACK + 1)]


def _basdt_to_date(bas_dt: str | None) -> date | None:
    """basDt(YYYYMMDD 문자열) → date. marcap_as_of 가 date 컬럼이라 str 그대로면 asyncpg DataError.

    파싱 불가/None 은 None(해당 행 marcap_as_of 만 NULL, marcap 은 정상 저장).
    """
    if not bas_dt:
        return None
    try:
        return date(int(bas_dt[:4]), int(bas_dt[4:6]), int(bas_dt[6:8]))
    except (ValueError, IndexError):
        return None


async def _fetch_marcap_page(
    client: httpx.AsyncClient, url: str, api_key: str, bas_dt: str
) -> list[dict]:
    """단일 시세 오퍼레이션을 basDt 로 페이징 조회해 raw item 리스트 반환(빈 응답이면 [])."""
    rows: list[dict] = []
    page = 1
    while True:
        res = await client.get(
            url,
            params={
                "serviceKey": api_key,
                "resultType": "json",
                "numOfRows": _PAGE_SIZE,
                "pageNo": page,
                "basDt": bas_dt,
            },
        )
        res.raise_for_status()
        items = (
            res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
        )
        if not items:
            break
        rows.extend(items)
        if len(items) < _PAGE_SIZE:
            break
        page += 1
    return rows


async def _fetch_with_basdt_fallback(
    client: httpx.AsyncClient, url: str, api_key: str
) -> tuple[list[dict], str | None]:
    """직전 영업일부터 거슬러 시도해 비어있지 않은 첫 응답과 그 basDt 를 반환.

    모든 후보가 빈 응답이면 ([], None).
    """
    for bas_dt in _recent_basdt_candidates():
        items = await _fetch_marcap_page(client, url, api_key, bas_dt)
        if items:
            return items, bas_dt
    return [], None


def _parse_marcap_item(it: dict) -> int | None:
    """시가총액(mrktTotAmt) → int. 결측/파싱불가는 None."""
    raw = (it.get("mrktTotAmt") or "").strip() if isinstance(it.get("mrktTotAmt"), str) else it.get("mrktTotAmt")
    if raw in (None, ""):
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_ticker(it: dict) -> str:
    """srtnCd → 종목코드(앞 'A' 제거 후 끝 6자리)."""
    return (it.get("srtnCd") or "").strip().lstrip("A")[-6:]


async def fetch_securities_products(
    api_key: str, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """증권상품시세(15094806) — ETF/ETN coverage·name·시총 조회.

    getETFPriceInfo, getETNPriceInfo 두 오퍼레이션을 basDt 직전 영업일 fallback 으로 호출한다.
    반환 item: {ticker, asset_name, market('ETF'|'ETN'), marcap, bas_dt}.

    ⚠️ 스파이크: 실제 응답 키 확인 필요 — srtnCd(코드)/itmsNm(종목명)/mrktTotAmt(시총)로 추정.
    serviceKey 가 예외 메시지로 새지 않도록 호출자(update_marcap)가 status code 만 로깅한다.
    """
    operations = [
        (f"{_SECURITIES_PRODUCT_BASE}/getETFPriceInfo", "ETF"),
        (f"{_SECURITIES_PRODUCT_BASE}/getETNPriceInfo", "ETN"),
    ]
    rows: list[dict] = []

    async def _run(c: httpx.AsyncClient) -> None:
        for url, market in operations:
            items, bas_dt = await _fetch_with_basdt_fallback(c, url, api_key)
            for it in items:
                ticker = _parse_ticker(it)
                name = (it.get("itmsNm") or "").strip()
                if not ticker:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "asset_name": name,
                        "market": market,
                        "marcap": _parse_marcap_item(it),
                        "bas_dt": bas_dt,
                    }
                )

    if client is None:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as owned:
            await _run(owned)
    else:
        await _run(client)
    return rows


async def fetch_stock_prices(
    api_key: str, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """주식시세(15094808) getStockPriceInfo — 주식 시가총액 조회.

    basDt 직전 영업일 fallback 으로 호출. 반환 item: {ticker, marcap, bas_dt}.

    ⚠️ 스파이크: 실제 응답 키 확인 필요 — srtnCd(코드)/mrktTotAmt(시총)로 추정.
    serviceKey 가 예외 메시지로 새지 않도록 호출자(update_marcap)가 status code 만 로깅한다.
    """
    rows: list[dict] = []

    async def _run(c: httpx.AsyncClient) -> None:
        items, bas_dt = await _fetch_with_basdt_fallback(c, _STOCK_PRICE_URL, api_key)
        for it in items:
            ticker = _parse_ticker(it)
            if not ticker:
                continue
            rows.append({"ticker": ticker, "marcap": _parse_marcap_item(it), "bas_dt": bas_dt})

    if client is None:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as owned:
            await _run(owned)
    else:
        await _run(client)
    return rows


# ─────────────────────────── marcap 적재 (always-run, fingerprint 우회) ───────────────────────────

_UPDATE_MARCAP_SQL = """
update stocks set marcap = $2, marcap_as_of = $3, updated_at = now()
where country_code = $1 and ticker = $4
"""

# 주식(KOSPI+KOSDAQ)만 시총 내림차순 순위. ETF/ETN·미적재는 NULL 로 리셋.
_RECALC_RANK_SQL = """
update stocks s set marcap_rank = r.rn
from (
    select ticker, row_number() over (order by marcap desc nulls last) rn
    from stocks
    where country_code = $1 and is_active and market in ('KOSPI', 'KOSDAQ') and marcap is not null
) r
where s.ticker = r.ticker and s.country_code = $1
"""


async def update_marcap(conn: Any, api_key: str, *, country_code: str = DEFAULT_COUNTRY) -> int:
    """주식시세·증권상품시세에서 시가총액을 UPDATE(기존 행만) — fingerprint skip 우회 always-run.

    - api_key 없으면 skip(coverage pipeline 과 동일 가드).
    - 빈 응답이면 기존 marcap 보존(UPDATE·rank 재계산 둘 다 skip).
    - 적재 후 marcap_rank 를 주식(KOSPI+KOSDAQ) 대상 window function 으로 재계산(spec verbatim SQL).

    반환: UPDATE 시도한 ticker 수.
    """
    if not api_key:
        print("  [marcap] api_key 미설정 — skip")
        return 0

    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
            stock_rows = await fetch_stock_prices(api_key, client=client)
            product_rows = await fetch_securities_products(api_key, client=client)
    except Exception as e:
        # serviceKey 가 URL 에 포함돼 예외 메시지로 새지 않도록 상태코드만 노출.
        status = getattr(getattr(e, "response", None), "status_code", None)
        print(f"  [marcap] 시세 조회 실패({f'HTTP {status}' if status else type(e).__name__}) — skip")
        return 0

    # ticker 별 marcap·basDt 머지(주식 + ETF/ETN). marcap None 은 제외(기존값 보존).
    merged: dict[str, tuple[int, str | None]] = {}
    for r in (*stock_rows, *product_rows):
        if r.get("ticker") and r.get("marcap") is not None:
            merged[r["ticker"]] = (r["marcap"], r.get("bas_dt"))

    if not merged:
        print("  [marcap] 빈 응답 — 기존 시총 보존, skip")
        return 0

    await conn.executemany(
        _UPDATE_MARCAP_SQL,
        [
            (country_code, marcap, _basdt_to_date(bas_dt), ticker)
            for ticker, (marcap, bas_dt) in merged.items()
        ],
    )
    await conn.execute(_RECALC_RANK_SQL, country_code)
    print(f"  [marcap] {len(merged)}건 갱신 + 순위 재계산")
    return len(merged)


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

    async def _securities() -> list[dict]:
        # 증권상품시세 = ETF/ETN coverage(FDR 대체). 하위(preserve) 소스라 신규 ticker(ETF/ETN)는
        # 이름과 함께 insert 되고, data_go_kr 가 이미 가진 ticker 는 canonical 보존 + 변형명 별칭.
        # marcap 은 여기서 무시(이름·market 만) — 시총은 always-run update_marcap 단계가 담당하므로
        # fingerprint(ticker|name|market)가 매일 변동 없이 안정적으로 유지된다(시세 재적재 방지).
        if not api_key:
            return []
        try:
            rows = await fetch_securities_products(api_key)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            print(f"  [securities] 실패({f'HTTP {status}' if status else type(e).__name__}) — skip")
            return []
        return [
            {"ticker": r["ticker"], "asset_name": r["asset_name"], "market": r["market"]}
            for r in rows
            if r.get("ticker") and r.get("asset_name")
        ]

    return [("data_go_kr", _dgk), ("securities", _securities)]


async def seed(db_url: str, *, api_key: str) -> None:
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        # 다중 인스턴스 동시 실행 가드 — Coolify scheduled task 는 replica 마다 cron 을 붙이므로
        # 같은 시각에 여러 인스턴스가 이 스크립트를 동시 실행할 수 있다. session advisory lock 을
        # 못 잡으면 이미 다른 인스턴스가 실행 중이니 즉시 no-op 으로 빠진다(deadlock·중복 Naver 호출 방지).
        if not await conn.fetchval("select pg_try_advisory_lock(hashtext('seed_stocks'))"):
            print("다른 인스턴스가 실행 중 — skip")
            return
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

        # 6) marcap 적재(always-run, fingerprint 우회) — 시총·순위 갱신
        await update_marcap(conn, api_key)

        print("완료.")
    finally:
        # session advisory lock 은 conn.close() 로 세션이 닫히면 자동 해제된다.
        await conn.close()


def main() -> None:
    settings = Settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        raise SystemExit("database_url 미설정")
    asyncio.run(seed(db_url, api_key=settings.data_go_kr_api_key))


if __name__ == "__main__":
    main()
