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

현재 소스: data.go.kr(공공데이터, 키 필요) — KRX상장종목정보(주식 authority, 보통주) + 주식시세(우선주 coverage)
+ 증권상품시세(ETF/ETN coverage) + 주식/증권상품시세 marcap. FDR 폐기.
"""

import asyncio
import hashlib
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any, Awaitable, Callable

import asyncpg
import httpx

from invest_note_api.config import DEFAULT_STOCK_SEED_SOURCES, Settings
from invest_note_api.domain.hangul import to_chosung
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY
from invest_note_api.external.constants import USER_AGENT
from invest_note_api.external.naver_search import search_kr
from invest_note_api.external.provider_registry import resolve_chain

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
# apis.data.go.kr 게이트웨이는 정상 응답도 느리고(0.7~20초) 종종 30초를 넘긴다. 느린 응답이
# ReadTimeout 으로 버려지지 않게 data.go.kr 호출 클라이언트는 timeout 을 넉넉히 둔다.
_DATA_GO_KR_TIMEOUT = 60
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


def _extract_items(payload: dict) -> list[dict]:
    """data.go.kr 응답 envelope 에서 item 리스트를 추출(정규화).

    공공데이터포털 공통 quirk:
      - 결과 1건이면 item 이 list 가 아닌 단일 dict 로 온다 → [item] 으로 정규화.
        (정규화 안 하면 `for it in items` 가 dict 키(str)를 돌아 it.get() 에서 AttributeError.)
      - 결과 0건이면 items 가 "" 또는 누락 → [].
    """
    body = payload.get("response", {}).get("body", {})
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, dict):
        return []  # items 가 ""/None/누락(0건)
    item = items.get("item", [])
    if isinstance(item, dict):
        return [item]
    return item if isinstance(item, list) else []


# apis.data.go.kr(금융위 1160100 게이트웨이)는 정상 응답도 14~18초로 느리고, 같은 요청이
# 404 HTML 오류페이지·무응답을 간헐적으로 반환한다(엔드포인트·키는 정상). 일시 장애로 보이는
# 상태코드/전송오류만 재시도한다.
_RETRYABLE_STATUS = {404, 408, 429, 500, 502, 503, 504}


async def _get_with_retry(
    client: httpx.AsyncClient, url: str, params: dict, *, retries: int = 6
) -> httpx.Response:
    """data.go.kr 게이트웨이 간헐 장애(404/타임아웃)를 backoff 재시도로 흡수.

    재시도 대상이 아닌 4xx(파라미터 오류 등)는 즉시 raise 한다. 마지막 시도 실패도 raise.
    """
    for attempt in range(retries):
        try:
            res = await client.get(url, params=params)
            res.raise_for_status()
            return res
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRYABLE_STATUS or attempt == retries - 1:
                raise
        except httpx.TransportError:
            if attempt == retries - 1:
                raise
        await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")  # 루프가 항상 return/raise 로 끝난다(타입체커용).


def _parse_item(it: dict) -> dict | None:
    """getItemInfo item → {ticker, asset_name, market}. ticker/name 결측은 None."""
    ticker = (it.get("srtnCd") or "").strip().lstrip("A")[-6:]
    name = (it.get("itmsNm") or "").strip()
    market = (it.get("mrktCtg") or "").strip()
    if ticker and name:
        return {"ticker": ticker, "asset_name": name, "market": market}
    return None


async def fetch_data_go_kr(api_key: str) -> list[dict]:
    """공공데이터포털 금융위 KRX상장종목정보 getItemInfo — 직전 영업일 basDt 의 전 종목 coverage.

    ⚠️ basDt 미지정 시 전체 과거 이력(수백만 행)이 와 사실상 무한 페이징이 된다. 반드시 직전
    영업일을 지정하고, 주말·휴장은 _recent_basdt_candidates 로 거슬러 fallback 한다.
    게이트웨이 간헐 404/타임아웃은 _get_with_retry 가 흡수한다.
    """
    rows: list[dict] = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT) as client:
        # basDt fallback: 첫 후보로 1페이지 받아 비어있지 않으면 그 basDt 로 확정 후 전 페이지 수집.
        items: list[dict] = []
        bas_dt: str | None = None
        for candidate in _recent_basdt_candidates():
            res = await _get_with_retry(
                client,
                _DATA_GO_KR_URL,
                {
                    "serviceKey": api_key,
                    "resultType": "json",
                    "numOfRows": _PAGE_SIZE,
                    "pageNo": 1,
                    "basDt": candidate,
                },
            )
            items = _extract_items(res.json())
            if items:
                bas_dt = candidate
                break
        if bas_dt is None:
            return []  # 최근 영업일 후보 전부 빈 응답
        rows.extend(r for it in items if (r := _parse_item(it)))

        page = 2
        while len(items) == _PAGE_SIZE:
            res = await _get_with_retry(
                client,
                _DATA_GO_KR_URL,
                {
                    "serviceKey": api_key,
                    "resultType": "json",
                    "numOfRows": _PAGE_SIZE,
                    "pageNo": page,
                    "basDt": bas_dt,
                },
            )
            items = _extract_items(res.json())
            rows.extend(r for it in items if (r := _parse_item(it)))
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
        res = await _get_with_retry(
            client,
            url,
            {
                "serviceKey": api_key,
                "resultType": "json",
                "numOfRows": _PAGE_SIZE,
                "pageNo": page,
                "basDt": bas_dt,
            },
        )
        items = _extract_items(res.json())
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
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT) as owned:
            await _run(owned)
    else:
        await _run(client)
    return rows


async def fetch_stock_prices(
    api_key: str, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """주식시세(15094808) getStockPriceInfo — 주식 시가총액 + 종목명/시장 조회.

    basDt 직전 영업일 fallback 으로 호출. 반환 item: {ticker, asset_name, market, marcap, bas_dt}.

    getItemInfo(authority)와 달리 우선주(005935 등, mrktCtg=KOSPI/KOSDAQ)를 포함하므로
    종목 마스터 보강 소스(stock_prices)로도 쓰인다. marcap 은 update_marcap 이 ticker 로만 머지한다.
    응답 키: srtnCd(코드)/itmsNm(종목명)/mrktCtg(시장)/mrktTotAmt(시총).
    """
    rows: list[dict] = []

    async def _run(c: httpx.AsyncClient) -> None:
        items, bas_dt = await _fetch_with_basdt_fallback(c, _STOCK_PRICE_URL, api_key)
        for it in items:
            ticker = _parse_ticker(it)
            if not ticker:
                continue
            rows.append({
                "ticker": ticker,
                "asset_name": (it.get("itmsNm") or "").strip(),
                "market": (it.get("mrktCtg") or "").strip(),
                "marcap": _parse_marcap_item(it),
                "bas_dt": bas_dt,
            })

    if client is None:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=_DATA_GO_KR_TIMEOUT) as owned:
            await _run(owned)
    else:
        await _run(client)
    return rows


# ─────────────────────────── marcap 적재 (always-run, fingerprint 우회) ───────────────────────────

_UPDATE_MARCAP_SQL = """
update stocks set marcap = $2, marcap_as_of = $3, updated_at = now()
where country_code = $1 and ticker = $4
"""

# 순위 집합에서 빠진 종목(상폐/ETF·ETN 재분류/marcap 결측)의 stale rank 를 먼저 NULL 로 리셋.
# _RECALC_RANK_SQL 은 자격 종목만 UPDATE 하므로, 이 리셋 없이는 빠진 종목이 옛 순위를 유지한다.
_RESET_RANK_SQL = """
update stocks set marcap_rank = null
where country_code = $1 and marcap_rank is not null
    and not (is_active and market in ('KOSPI', 'KOSDAQ') and marcap is not null)
"""

# 주식(KOSPI+KOSDAQ)만 시총 내림차순 순위. ETF/ETN·미적재·상폐는 위 리셋으로 NULL 유지.
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
    - 적재 후 순위 집합에서 빠진 종목의 stale rank 를 리셋하고, 주식(KOSPI+KOSDAQ) 대상
      window function 으로 marcap_rank 를 재계산한다.

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
    await conn.execute(_RESET_RANK_SQL, country_code)
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
            if not results:
                return  # 빈 응답(네트워크/rate-limit 추정) → 미체크(다음 run 재시도)
            # Naver 가 응답함 → 정확 코드 매칭이 없어도 "검증함"으로 기록한다.
            # (미발견까지 재질의하면 Naver 에 없는 종목을 매 run 무한 재조회 → 수렴 안 함.)
            checked.append(ticker)
            match = next((r for r in results if r["code"] == ticker), None)
            if match is None:
                return  # 응답엔 있으나 해당 코드 없음 → 별칭/시장 보강 없이 종료
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


# 기본 소스 체인 — config.DEFAULT_STOCK_SEED_SOURCES 단일 출처(Settings 기본값과 drift 방지).
_DEFAULT_SEED_SOURCES = DEFAULT_STOCK_SEED_SOURCES


def _build_pipeline(
    api_key: str, sources: Sequence[str] = _DEFAULT_SEED_SOURCES
) -> list[tuple[str, Callable[[], Awaitable[list[dict]]]]]:
    """소스 우선순위 파이프라인. 첫 소스가 canonical authority. 실패 소스는 [] 반환.

    `sources` 는 env STOCK_SEED_SOURCES 에서 온 이름 체인 — registry 에 없는 이름은
    ValueError. marcap(always-run)·Naver 교차검증은 토글 대상이 아닌 고정 단계(seed 참고).
    """

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

    async def _stock_prices() -> list[dict]:
        # 주식시세 = 우선주 coverage. authority(getItemInfo)는 우선주를 반환하지 않으므로,
        # 하위(preserve) 소스로 우선주(005935 등) 신규 ticker 를 이름·시장과 함께 보강한다.
        # 기존 보통주 ticker 는 canonical 보존 + 변형명 별칭. marcap 은 여기서 무시(이름·market 만)
        # — 시총은 always-run update_marcap 단계가 담당(fingerprint 안정성).
        if not api_key:
            return []
        try:
            rows = await fetch_stock_prices(api_key)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            print(f"  [stock_prices] 실패({f'HTTP {status}' if status else type(e).__name__}) — skip")
            return []
        return [
            {"ticker": r["ticker"], "asset_name": r["asset_name"], "market": r["market"]}
            for r in rows
            if r.get("ticker") and r.get("asset_name")
        ]

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

    registry: dict[str, Callable[[], Awaitable[list[dict]]]] = {
        "data_go_kr": _dgk,
        "stock_prices": _stock_prices,
        "securities": _securities,
    }
    return list(zip(sources, resolve_chain(sources, registry, domain="stock_seed")))


async def seed(db_url: str, *, api_key: str, sources: Sequence[str] | None = None) -> None:
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
        all_sources_ok = True    # 한 소스라도 빈/실패 응답이면 union 이 불완전 → soft-delete 위험
        authority_used = False   # 첫 번째로 데이터를 반환한 소스 = canonical authority(overwrite)
        upstream_changed = False  # 앞선 소스가 바뀌면 canonical 이 이동했을 수 있어 하위 변형명 재계산 필요

        # 1~2) 소스 순차 병합 (authority=이름 확립, 이후=신규 추가 + 변형명 별칭)
        for name, fetch in _build_pipeline(api_key, sources or _DEFAULT_SEED_SOURCES):
            rows = await fetch()
            if not rows:
                # 빈 응답(API 실패/키 미설정/일시 장애) → 이 소스의 종목이 union 에서 누락된다.
                all_sources_ok = False
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

        # 3) soft-delete — 모든 소스가 정상 응답(union 완전)했고 변경이 있을 때만.
        # 한 소스라도 빈/실패 응답이면 그 소스의 종목이 union 에서 통째로 빠져, 실제로는
        # 존재하는 종목(예: ETF/ETN 소스 실패 시 전 ETF, authority 실패 시 전 주식)을 대량
        # 오상폐할 수 있으므로 skip 한다. 누락분은 다음 정상 run 에서 다시 활성화/정리된다.
        if not all_sources_ok:
            print("  [soft-delete] 일부 소스 빈/실패 응답 — union 불완전, skip(대량 오상폐 방지)")
        elif any_changed and union:
            print(f"  [soft-delete] {await soft_delete_not_in(conn, DEFAULT_COUNTRY, union)}건")
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
    asyncio.run(
        seed(db_url, api_key=settings.data_go_kr_api_key, sources=settings.stock_seed_source_list)
    )


if __name__ == "__main__":
    main()
