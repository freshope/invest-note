"""stock_seed 시세 fetcher · basDt fallback · admin 토큰 검증 테스트.

네트워크 의존은 httpx.MockTransport 로 차단. DB 통합(marcap_rank window)은 실DB 미사용이라 생략.
"""
from __future__ import annotations

import httpx
import pytest

from invest_note_api.services import stock_seed


def _body(items: list[dict]) -> dict:
    """data.go.kr JSON 응답 envelope 로 감싼다."""
    return {"response": {"body": {"items": {"item": items}}}}


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ─────────────────────────── fetch_stock_prices ───────────────────────────


async def test_fetch_stock_prices_parses_ticker_marcap_name_market():
    def handler(req: httpx.Request) -> httpx.Response:
        # 첫 후보 basDt 에서 바로 응답. 우선주(005935)도 mrktCtg 와 함께 포함.
        return httpx.Response(
            200,
            json=_body(
                [
                    {"srtnCd": "A005930", "itmsNm": "삼성전자", "mrktCtg": "KOSPI", "mrktTotAmt": "400000000000000"},
                    {"srtnCd": "A005935", "itmsNm": "삼성전자우", "mrktCtg": "KOSPI", "mrktTotAmt": "50000000000000"},
                ]
            ),
        )

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_stock_prices("key", client=client)

    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["005930"]["marcap"] == 400000000000000
    # 우선주 종목명/시장이 종목 마스터 보강에 쓰이도록 파싱된다.
    assert by_ticker["005935"]["asset_name"] == "삼성전자우"
    assert by_ticker["005935"]["market"] == "KOSPI"
    assert all(r["bas_dt"] for r in rows)


async def test_fetch_stock_prices_empty_response_returns_empty():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_stock_prices("key", client=client)

    assert rows == []


async def test_fetch_stock_prices_pages_through_full_pages():
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params["pageNo"])
        calls.append(page)
        if page == 1:
            items = [{"srtnCd": f"{i:06d}", "mrktTotAmt": "1000"} for i in range(stock_seed._PAGE_SIZE)]
            return httpx.Response(200, json=_body(items))
        return httpx.Response(200, json=_body([{"srtnCd": "999999", "mrktTotAmt": "2000"}]))

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_stock_prices("key", client=client)

    assert calls[:2] == [1, 2]
    assert len(rows) == stock_seed._PAGE_SIZE + 1
    assert rows[-1]["ticker"] == "999999"
    assert rows[-1]["marcap"] == 2000


# ─────────────────────────── fetch_securities_products ───────────────────────────


async def test_fetch_securities_products_tags_etf_and_etn():
    def handler(req: httpx.Request) -> httpx.Response:
        if "getETFPriceInfo" in str(req.url):
            return httpx.Response(
                200, json=_body([{"srtnCd": "069500", "itmsNm": "KODEX 200", "mrktTotAmt": "5000000"}])
            )
        if "getETNPriceInfo" in str(req.url):
            return httpx.Response(
                200, json=_body([{"srtnCd": "530031", "itmsNm": "신한 ETN", "mrktTotAmt": "300000"}])
            )
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_securities_products("key", client=client)

    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["069500"]["market"] == "ETF"
    assert by_ticker["069500"]["marcap"] == 5000000
    assert by_ticker["069500"]["asset_name"] == "KODEX 200"
    assert by_ticker["530031"]["market"] == "ETN"
    assert by_ticker["530031"]["marcap"] == 300000


async def test_fetch_securities_products_missing_marcap_is_none():
    def handler(req: httpx.Request) -> httpx.Response:
        if "getETFPriceInfo" in str(req.url):
            return httpx.Response(200, json=_body([{"srtnCd": "069500", "itmsNm": "KODEX 200"}]))
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_securities_products("key", client=client)

    assert rows[0]["marcap"] is None


# ─────────────────────────── 단일 item dict quirk ───────────────────────────


def test_extract_items_normalizes_single_item_dict():
    # data.go.kr 는 결과 1건이면 item 을 list 가 아닌 단일 dict 로 준다 → [item] 정규화.
    one = {"response": {"body": {"items": {"item": {"srtnCd": "005930"}}}}}
    assert stock_seed._extract_items(one) == [{"srtnCd": "005930"}]


def test_extract_items_handles_list_and_empty_shapes():
    many = {"response": {"body": {"items": {"item": [{"srtnCd": "A"}, {"srtnCd": "B"}]}}}}
    assert stock_seed._extract_items(many) == [{"srtnCd": "A"}, {"srtnCd": "B"}]
    # 0건이면 items 가 "" 로 오기도 한다 → [].
    assert stock_seed._extract_items({"response": {"body": {"items": ""}}}) == []
    assert stock_seed._extract_items({"response": {"body": {}}}) == []
    assert stock_seed._extract_items({}) == []


async def test_fetch_stock_prices_handles_single_item_dict():
    # 한 페이지에 종목이 1건이면 item 이 단일 dict — 과거엔 for-loop 가 키를 돌아 크래시했다.
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"response": {"body": {"items": {"item": {"srtnCd": "A005930", "mrktTotAmt": "100"}}}}},
        )

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_stock_prices("key", client=client)

    assert len(rows) == 1
    assert rows[0]["ticker"] == "005930"
    assert rows[0]["marcap"] == 100


# ─────────────────────────── basDt fallback ───────────────────────────


async def test_basdt_fallback_retries_earlier_dates_on_empty():
    """첫 후보(직전일)가 빈 응답이면 이전 날짜를 시도하고, 첫 비어있지 않은 응답을 채택."""
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        bas_dt = req.url.params["basDt"]
        seen.append(bas_dt)
        # 처음 2개 후보는 빈 응답(주말/미발행), 3번째에 데이터.
        if len(seen) <= 2:
            return httpx.Response(200, json=_body([]))
        return httpx.Response(200, json=_body([{"srtnCd": "005930", "mrktTotAmt": "100"}]))

    async with _mock_client(handler) as client:
        items, bas_dt = await stock_seed._fetch_with_basdt_fallback(
            client, stock_seed._STOCK_PRICE_URL, "key"
        )

    assert len(seen) == 3
    assert bas_dt == seen[2]
    assert items[0]["srtnCd"] == "005930"


async def test_basdt_fallback_all_empty_returns_none():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        items, bas_dt = await stock_seed._fetch_with_basdt_fallback(
            client, stock_seed._STOCK_PRICE_URL, "key"
        )

    assert items == []
    assert bas_dt is None


def test_pipeline_order_authority_then_stock_prices_then_securities():
    # data_go_kr(authority, 보통주) 다음에 stock_prices(우선주 보강), securities(ETF/ETN) 순.
    # authority 가 첫 소스여야 종목명이 canonical 로 확립되고, 우선주는 preserve 로 보강된다.
    names = [name for name, _ in stock_seed._build_pipeline("key")]
    assert names == ["data_go_kr", "stock_prices", "securities"]


def test_pipeline_sources_env_order_respected():
    # env STOCK_SEED_SOURCES 로 순서를 바꾸면 파이프라인이 그 순서를 따른다 —
    # 첫 항목이 authority 가 되는 계약(seed 의 is_authority)이 env 로 제어 가능.
    names = [name for name, _ in stock_seed._build_pipeline("key", ["securities", "data_go_kr"])]
    assert names == ["securities", "data_go_kr"]


def test_pipeline_unknown_source_raises_value_error():
    # registry 에 없는 소스명(env 오타) → ValueError fail-fast.
    import pytest

    with pytest.raises(ValueError, match="stock_seed"):
        stock_seed._build_pipeline("key", ["fdr"])


def test_validate_seed_sources_trigger_time_fail_fast():
    # admin 트리거 시점 검증 — 오타는 ValueError(라우터가 400 변환), 빈 체인은 기본 소스 허용.
    import pytest

    stock_seed.validate_seed_sources(["kis", "data_go_kr"])
    stock_seed.validate_seed_sources([])  # 빈 체인 → 기본 소스(seed 와 동일 규칙)
    with pytest.raises(ValueError, match="stock_seed"):
        stock_seed.validate_seed_sources(["fdr"])


def test_validate_us_seed_sources_fail_fast():
    # US 종목 마스터 소스도 KR 과 동일 registry/env 구조 — 오타는 ValueError, 빈 체인은 기본 소스.
    import pytest

    stock_seed.validate_us_seed_sources(["nasdaqtrader"])
    stock_seed.validate_us_seed_sources([])  # 빈 체인 → 기본 소스
    with pytest.raises(ValueError, match="us_stock_seed"):
        stock_seed.validate_us_seed_sources(["nyse"])


def test_recent_basdt_candidates_are_descending_and_bounded():
    cands = stock_seed._recent_basdt_candidates()
    assert len(cands) == stock_seed._BASDT_MAX_LOOKBACK
    # 최신(직전일)이 먼저, 거슬러 갈수록 작아진다.
    assert cands == sorted(cands, reverse=True)


def test_basdt_to_date_converts_yyyymmdd():
    # marcap_as_of 는 date 컬럼 — basDt 문자열을 date 로 변환해야 asyncpg DataError 가 안 난다.
    from datetime import date

    assert stock_seed._basdt_to_date("20260530") == date(2026, 5, 30)
    assert stock_seed._basdt_to_date(None) is None
    assert stock_seed._basdt_to_date("") is None


# ─────────────────────────── backfill_us_aliases ───────────────────────────


class _FakeConn:
    """backfill_us_aliases 의 trades/stocks 쿼리·executemany 만 흉내내는 최소 stub."""

    def __init__(self, traded: list[str], universe: set[str]) -> None:
        self.traded = traded
        self.universe = universe  # stocks 에 실재하는 US 티커
        self.upserted: list[tuple] = []

    async def fetch(self, sql: str, *args):
        if "from trades" in sql:
            return [{"ticker_symbol": t} for t in self.traded]
        if "from stocks" in sql:
            requested = set(args[1])  # _existing_tickers(country, tickers)
            return [{"ticker": t} for t in requested & self.universe]
        raise AssertionError(f"예상치 못한 쿼리: {sql}")

    async def executemany(self, _sql: str, tuples) -> None:
        self.upserted.extend(tuples)


async def test_backfill_us_aliases_unions_popular_and_traded(monkeypatch):
    from invest_note_api.domain.hangul import to_chosung
    from invest_note_api.domain.trade_types import COUNTRY_US

    # 거래이력에 비인기 종목 TRD(실재) + 미실재 ZZZZ. 인기 리스트의 AAPL 도 실재.
    conn = _FakeConn(traded=["TRD", "ZZZZ"], universe={"AAPL", "TRD"})

    captured: dict = {}

    async def fake_names(tickers, *, client=None):
        captured["asked"] = list(tickers)
        return {t: f"한글{t}" for t in tickers}

    monkeypatch.setattr(stock_seed, "_naver_us_korean_names", fake_names)

    n = await stock_seed.backfill_us_aliases(conn)

    # Naver 조회 대상 = (인기 ∪ 거래) ∩ 실재 = {AAPL, TRD} (미실재 ZZZZ 제외, 정렬됨)
    assert captured["asked"] == ["AAPL", "TRD"]
    assert n == 2
    # source='naver', alias_chosung 계산 포함해 적재
    assert {t[1] for t in conn.upserted} == {"AAPL", "TRD"}
    aapl = next(t for t in conn.upserted if t[1] == "AAPL")
    assert aapl == (COUNTRY_US, "AAPL", "한글AAPL", to_chosung("한글AAPL"), "naver")


async def test_backfill_us_aliases_no_existing_tickers_skips_naver(monkeypatch):
    conn = _FakeConn(traded=[], universe=set())

    async def fail_names(tickers, *, client=None):
        raise AssertionError("실재 티커가 없으면 Naver 를 호출하면 안 된다")

    monkeypatch.setattr(stock_seed, "_naver_us_korean_names", fail_names)

    assert await stock_seed.backfill_us_aliases(conn) == 0
    assert conn.upserted == []
    assert stock_seed._basdt_to_date("bad") is None


# ─────────────────────────── require_admin_token ───────────────────────────


def _admin_client(admin_token: str):
    from fastapi.testclient import TestClient

    from invest_note_api.config import Settings, get_settings
    from invest_note_api.main import create_app

    settings = Settings(supabase_url="https://test.supabase.co", admin_token=admin_token)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_admin_seed_rejects_missing_token():
    client = _admin_client("secret")
    r = client.post("/admin/seed/stocks")
    assert r.status_code == 403


def test_admin_seed_rejects_wrong_token():
    client = _admin_client("secret")
    r = client.post("/admin/seed/stocks", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 403


def test_admin_seed_rejects_when_token_unset_even_with_empty_header():
    # admin_token 미설정 → compare_digest("","") 함정 방어. 빈 헤더로도 통과하면 안 된다.
    client = _admin_client("")
    r = client.post("/admin/seed/stocks", headers={"X-Admin-Token": ""})
    assert r.status_code == 403


def test_admin_seed_accepts_valid_token_returns_202(monkeypatch):
    # run_seed 가 실제 DB 에 연결하지 않도록 BackgroundTasks 진입점을 no-op 으로 교체.
    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr("invest_note_api.routers.admin.run_seed", noop)
    client = _admin_client("secret")
    r = client.post("/admin/seed/stocks", headers={"X-Admin-Token": "secret"})
    assert r.status_code == 202
    assert r.json() == {"status": "started"}


# ─────────────────────────── _get_with_retry (게이트웨이 간헐 장애) ───────────────────────────


async def _instant_sleep(*_a):
    return None


async def test_get_with_retry_retries_transient_404_then_succeeds(monkeypatch):
    monkeypatch.setattr(stock_seed.asyncio, "sleep", _instant_sleep)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(404, text="<html>gateway error</html>")
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        res = await stock_seed._get_with_retry(client, "https://x", {"a": 1})
    assert res.status_code == 200
    assert calls["n"] == 2  # 첫 404 → 재시도 → 200


async def test_get_with_retry_raises_on_non_retryable_4xx(monkeypatch):
    monkeypatch.setattr(stock_seed.asyncio, "sleep", _instant_sleep)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={})  # 파라미터 오류는 재시도 대상 아님 → 즉시 raise

    async with _mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await stock_seed._get_with_retry(client, "https://x", {})


# ─────────────────────────── fetch_data_go_kr (basDt 필수) ───────────────────────────


def _patch_internal_client(monkeypatch, handler):
    """fetch_data_go_kr 가 자체 생성하는 httpx.AsyncClient 를 MockTransport 로 교체."""
    real = httpx.AsyncClient  # 패치 전 원본 캡처(자기참조 재귀 방지)
    monkeypatch.setattr(
        stock_seed.httpx,
        "AsyncClient",
        lambda *a, **k: real(transport=httpx.MockTransport(handler)),
    )


async def test_fetch_data_go_kr_sends_basdt_and_parses(monkeypatch):
    monkeypatch.setattr(stock_seed.asyncio, "sleep", _instant_sleep)
    seen = {"basDt": None}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["basDt"] = req.url.params.get("basDt")
        if req.url.params.get("pageNo") == "1":
            return httpx.Response(
                200, json=_body([{"srtnCd": "A005930", "itmsNm": "삼성전자", "mrktCtg": "KOSPI"}])
            )
        return httpx.Response(200, json=_body([]))

    _patch_internal_client(monkeypatch, handler)
    rows = await stock_seed.fetch_data_go_kr("key")
    assert seen["basDt"] and len(seen["basDt"]) == 8  # basDt(YYYYMMDD) 전달됨
    assert rows == [{"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"}]


async def test_fetch_data_go_kr_falls_back_when_first_basdt_empty(monkeypatch):
    monkeypatch.setattr(stock_seed.asyncio, "sleep", _instant_sleep)
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        bd = req.url.params.get("basDt")
        seen.append(bd)
        if bd == seen[0]:  # 첫 후보(최신 영업일)는 빈 응답 → 다음 후보로 fallback
            return httpx.Response(200, json=_body([]))
        if req.url.params.get("pageNo") == "1":
            return httpx.Response(
                200, json=_body([{"srtnCd": "000660", "itmsNm": "SK하이닉스", "mrktCtg": "KOSPI"}])
            )
        return httpx.Response(200, json=_body([]))

    _patch_internal_client(monkeypatch, handler)
    rows = await stock_seed.fetch_data_go_kr("key")
    assert rows == [{"ticker": "000660", "asset_name": "SK하이닉스", "market": "KOSPI"}]
    assert len(set(seen)) >= 2  # 최소 2개 basDt 후보 시도


# ─────────────────────────── KIS 종목마스터 ───────────────────────────


def _mst_line(ticker: str, name: str, group: str, tail_len: int) -> str:
    """KIS .mst 행 합성 — 앞부분(단축코드9+표준코드12+한글명) + 뒷부분 고정폭(그룹코드2+패딩)."""
    return f"{ticker:<9}{'KR7' + ticker + '003':<12}{name}" + group + "0" * (tail_len - 2)


def test_parse_kis_master_offsets_groups_and_filters():
    text = "\n".join(
        [
            _mst_line("005930", "삼성전자", "ST", 227),
            _mst_line("371460", "TIGER 차이나전기차", "EF", 227),  # ETF 재분류
            _mst_line("530031", "삼성 레버리지 ETN", "EN", 227),  # ETN 재분류
            _mst_line("58J297", "한국JR297호", "EW", 227),  # ELW — 제외
            _mst_line("Q50001", "KONEX형 코드", "ST", 227)[1:],  # 깨진 행(길이 부족) — skip
        ]
    )
    rows = stock_seed._parse_kis_master(text, "KOSPI", 227)
    assert {(r["ticker"], r["market"]) for r in rows} == {
        ("005930", "KOSPI"),
        ("371460", "ETF"),
        ("530031", "ETN"),
    }
    assert next(r for r in rows if r["ticker"] == "005930")["asset_name"] == "삼성전자"


def test_parse_kis_master_etn_q_prefix_and_alnum_etf():
    # 실파일 실측(2026-06-07): ETN 은 'Q' 접두 7자(Q500061→500061),
    # 신형 ETF 는 영숫자 6자(0000D0) — isdigit 필터를 쓰면 전부 탈락한다.
    text = "\n".join(
        [
            _mst_line("Q500061", "신한 인버스 ETN", "EN", 227),
            _mst_line("0000D0", "TIGER 엔비디아", "EF", 227),
            _mst_line("AB12", "코드 4자리", "ST", 227),  # 6자 미만 — 제외
        ]
    )
    rows = stock_seed._parse_kis_master(text, "KOSPI", 227)
    assert {(r["ticker"], r["market"]) for r in rows} == {("500061", "ETN"), ("0000D0", "ETF")}


async def test_fetch_kis_master_downloads_zips_and_merges(monkeypatch):
    import io
    import zipfile

    def _zip_bytes(inner_name: str, text: str) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(inner_name, text.encode("cp949"))
        return buf.getvalue()

    kospi_zip = _zip_bytes("kospi_code.mst", _mst_line("005930", "삼성전자", "ST", 227))
    kosdaq_zip = _zip_bytes("kosdaq_code.mst", _mst_line("247540", "에코프로비엠", "ST", 221))

    def handler(req: httpx.Request) -> httpx.Response:
        if "kospi_code.mst.zip" in str(req.url):
            return httpx.Response(200, content=kospi_zip)
        if "kosdaq_code.mst.zip" in str(req.url):
            return httpx.Response(200, content=kosdaq_zip)
        return httpx.Response(404)

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_kis_master(client=client)

    assert rows == [
        {"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"},
        {"ticker": "247540", "asset_name": "에코프로비엠", "market": "KOSDAQ"},
    ]


def test_pipeline_kis_source_registered():
    # env STOCK_SEED_SOURCES 에 kis 를 넣으면 파이프라인에 포함된다(api_key 불필요 소스).
    names = [name for name, _ in stock_seed._build_pipeline("", ["kis", "securities"])]
    assert names == ["kis", "securities"]


# ─────────────────────────── 교차검증 provider 토글 ───────────────────────────


class _CrossvalConn:
    """crossvalidate_stocks 용 FakeConn — 미검증 종목 fetch + checked update 기록."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.checked_args: list = []

    async def fetch(self, q, *a):
        return self.rows

    async def execute(self, q, *a):
        if "naver_checked_at" in q:
            self.checked_args.append(a)


def _patch_alias_recorder(monkeypatch) -> list[dict]:
    recorded: list[dict] = []

    async def fake_upsert_aliases(conn, aliases, **kw):
        recorded.extend(aliases)
        return len(aliases)

    monkeypatch.setattr(stock_seed, "upsert_aliases", fake_upsert_aliases)
    return recorded


async def test_crossvalidate_kis_master_batch_compare(monkeypatch):
    """kis provider — 마스터 파일 일괄 대조: 이름 변형→별칭, 시장 불일치 집계, 전원 checked."""

    async def fake_master(**kw):
        return [
            {"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"},
            {"ticker": "123456", "asset_name": "새이름", "market": "KOSPI"},
            {"ticker": "371460", "asset_name": "TIGER 차이나전기차", "market": "ETF"},
        ]

    monkeypatch.setattr(stock_seed, "fetch_kis_master", fake_master)
    aliases = _patch_alias_recorder(monkeypatch)
    conn = _CrossvalConn(
        [
            {"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"},  # 일치
            {"ticker": "123456", "asset_name": "옛이름", "market": "KOSPI"},  # 이름 변형
            {"ticker": "371460", "asset_name": "TIGER 차이나전기차", "market": "KOSPI"},  # 시장 불일치
            {"ticker": "999999", "asset_name": "코넥스종목", "market": "KONEX"},  # 파일에 없음
        ]
    )

    n, mm, ck = await stock_seed.crossvalidate_stocks(conn, provider="kis")

    assert aliases == [{"ticker": "123456", "alias": "새이름", "source": "kis"}]
    assert (n, mm) == (1, 1)
    assert ck == 4  # 파일에 없는 코드(KONEX 등)도 검증함 — 재질의 무의미
    assert sorted(conn.checked_args[0][1]) == ["005930", "123456", "371460", "999999"]


async def test_crossvalidate_kis_download_failure_keeps_unchecked(monkeypatch):
    """마스터 다운로드 실패 → 전체 미체크(다음 run 재시도), 별칭/checked 기록 없음."""

    async def failing_master(**kw):
        raise RuntimeError("download fail")

    monkeypatch.setattr(stock_seed, "fetch_kis_master", failing_master)
    aliases = _patch_alias_recorder(monkeypatch)
    conn = _CrossvalConn([{"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"}])

    n, mm, ck = await stock_seed.crossvalidate_stocks(conn, provider="kis")

    assert (n, mm, ck) == (0, 0, 0)
    assert aliases == []
    assert conn.checked_args == []


async def test_crossvalidate_naver_per_ticker_lookup(monkeypatch):
    """naver provider — 종목별 조회: 응답 종목만 checked, 정확 코드 매칭만 별칭/시장 대조."""

    async def fake_search_kr(q, *, client=None):
        if q == "005930":
            return [{"code": "005930", "name": "삼성전자우", "market": "KR", "exchange": "KOSPI"}]
        return []  # rate-limit/미응답 → 미체크

    monkeypatch.setattr(stock_seed, "search_kr", fake_search_kr)
    aliases = _patch_alias_recorder(monkeypatch)
    conn = _CrossvalConn(
        [
            {"ticker": "005930", "asset_name": "삼성전자", "market": "KOSPI"},
            {"ticker": "999999", "asset_name": "미응답종목", "market": "KOSDAQ"},
        ]
    )

    n, mm, ck = await stock_seed.crossvalidate_stocks(conn, provider="naver")

    assert aliases == [{"ticker": "005930", "alias": "삼성전자우", "source": "naver"}]
    assert (n, mm, ck) == (1, 0, 1)
    assert conn.checked_args[0][1] == ["005930"]


async def test_crossvalidate_unknown_provider_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="crossvalidate"):
        await stock_seed.crossvalidate_stocks(_CrossvalConn([]), provider="kisss")


# ─────────────────────────── US nasdaqtrader 파서/fetch ───────────────────────────

_NASDAQ_LISTED = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
    "QQQ|Invesco QQQ Trust|Q|N|N|100|Y|N\n"
    "TEST|NASDAQ TEST STOCK|Q|Y|N|100|N|N\n"
    "ZVZZT|NASDAQ TEST|Q|N|N|100|N|N\n"
    "File Creation Time: 0608202618:00|||||||\n"
)

_OTHER_LISTED = (
    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
    "IBM|International Business Machines|N|IBM|N|100|N|IBM\n"
    "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY\n"
    "BRK.A|Berkshire Hathaway Class A|N|BRK A|N|10|N|BRK.A\n"
    "File Creation Time: 0608202618:00|||||||\n"
)


def test_parse_nasdaqtrader_nasdaq_listed():
    rows = stock_seed._parse_nasdaqtrader(_NASDAQ_LISTED, nasdaq_default="NASDAQ")
    by_ticker = {r["ticker"]: r for r in rows}
    # Test Issue=Y(TEST) 제외, 보드는 NASDAQ, 통화 USD
    assert "TEST" not in by_ticker
    assert by_ticker["AAPL"]["market"] == "NASDAQ"
    assert by_ticker["AAPL"]["currency"] == "USD"
    assert by_ticker["QQQ"]["asset_name"].startswith("Invesco QQQ")


def test_parse_nasdaqtrader_other_listed_maps_exchange_and_accepts_class_share():
    rows = stock_seed._parse_nasdaqtrader(_OTHER_LISTED)
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["IBM"]["market"] == "NYSE"     # N → NYSE
    assert by_ticker["SPY"]["market"] == "NYSE ARCA"  # P → NYSE ARCA
    assert "BRK.A" in by_ticker  # 클래스주(.A) 허용


def test_parse_nasdaqtrader_class_share_filter_matrix():
    """클래스주(.A/.B/.C) 채택, 워런트/유닛/우선주/특수기호 제외 회귀."""
    text = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
        "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
        "BRK.B|Berkshire Hathaway Class B|Q|N|N|100|N|N\n"
        "BF.B|Brown-Forman Class B|Q|N|N|100|N|N\n"
        "ABC.WS|Warrant|Q|N|N|100|N|N\n"
        "XYZ.U|Unit|Q|N|N|100|N|N\n"
        "FOO$|Preferred|Q|N|N|100|N|N\n"
        "BAR=|When Issued|Q|N|N|100|N|N\n"
        "TST.A|Test Issue Class A|Q|Y|N|100|N|N\n"
    )
    tickers = {r["ticker"] for r in stock_seed._parse_nasdaqtrader(text, nasdaq_default="NASDAQ")}
    assert tickers == {"AAPL", "BRK.B", "BF.B"}  # 클래스주+보통주만, Test Issue=Y(TST.A) 제외


def test_parse_nasdaqtrader_preferred_and_rights_filter_matrix():
    """클래스주(BRK.B/BF.B)+우선주(BAC$B) 채택, 워런트/유닛/rights 제외, 보통주(AAPL) 회귀.

    otherlisted 양식(ACT Symbol 첫 컬럼) — 우선주는 `$`+단일 시리즈 문자만 채택.
    """
    text = (
        "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
        "AAPL|Apple Inc.|Q|AAPL|N|100|N|AAPL\n"
        "BRK.B|Berkshire Hathaway Class B|N|BRK B|N|100|N|N\n"
        "BF.B|Brown-Forman Class B|N|BF B|N|100|N|N\n"
        "BAC$B|Bank of America Pref B|N|BAC PRB|N|100|N|N\n"
        "ABC.WS|Warrant|N|ABC WS|N|100|N|N\n"
        "XYZ.U|Unit|N|XYZ U|N|100|N|N\n"
        "AIIA.R|Rights|N|AIIA R|N|100|N|N\n"
    )
    tickers = {r["ticker"] for r in stock_seed._parse_nasdaqtrader(text)}
    assert tickers == {"AAPL", "BRK.B", "BF.B", "BAC$B"}


def test_parse_nasdaqtrader_skips_footer_and_empty():
    assert stock_seed._parse_nasdaqtrader("") == []
    assert stock_seed._parse_nasdaqtrader("Symbol|Security Name|Test Issue\n") == []


async def test_fetch_nasdaq_us_merges_both_files():
    def handler(req: httpx.Request) -> httpx.Response:
        if "nasdaqlisted" in str(req.url):
            return httpx.Response(200, text=_NASDAQ_LISTED)
        return httpx.Response(200, text=_OTHER_LISTED)

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_nasdaq_us(client=client)

    tickers = {r["ticker"] for r in rows}
    assert {"AAPL", "QQQ", "IBM", "SPY"} <= tickers
    assert all(r["currency"] == "USD" for r in rows)


# ─────────────────────────── seed_us advisory-lock / 빈응답 가드 ───────────────────────────


class _SeedUsConn:
    """seed_us 의 전 DB 메서드를 spy — advisory-lock skip / 빈응답 soft_delete 미호출 검증용."""

    def __init__(self, lock_acquired: bool):
        self._lock_acquired = lock_acquired
        self.fetchval_calls: list[str] = []
        self.execute_calls: list[str] = []
        self.executemany_calls: list[str] = []
        self.fetch_calls: list[str] = []
        self.closed = False

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append(sql)
        if "pg_try_advisory_lock" in sql:
            return self._lock_acquired
        return None

    async def execute(self, sql, *args):
        self.execute_calls.append(sql)
        return "DELETE 0"

    async def executemany(self, sql, args):
        self.executemany_calls.append(sql)

    async def fetch(self, sql, *args):
        self.fetch_calls.append(sql)
        return []

    async def close(self):
        self.closed = True


def _patch_seed_us(monkeypatch, conn, rows):
    async def fake_connect(*a, **kw):
        return conn

    async def fake_fetch_nasdaq_us(*, client=None):
        return rows

    monkeypatch.setattr(stock_seed.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(stock_seed, "fetch_nasdaq_us", fake_fetch_nasdaq_us)


async def test_seed_us_skips_when_advisory_lock_not_acquired(monkeypatch):
    """다른 인스턴스가 lock 보유(pg_try_advisory_lock=false) → fetch/upsert/soft_delete 미수행."""
    conn = _SeedUsConn(lock_acquired=False)
    fetched = {"hit": False}

    async def must_not_fetch(*, client=None):
        fetched["hit"] = True
        return [{"ticker": "AAPL", "asset_name": "Apple", "market": "NASDAQ",
                 "exchange": "NASDAQ", "currency": "USD"}]

    monkeypatch.setattr(stock_seed.asyncpg, "connect", lambda *a, **kw: _async_return(conn))
    monkeypatch.setattr(stock_seed, "fetch_nasdaq_us", must_not_fetch)

    await stock_seed.seed_us("postgresql://x")

    assert fetched["hit"] is False, "lock 미획득인데 nasdaqtrader fetch 가 실행됨"
    assert conn.executemany_calls == []  # upsert 없음
    assert conn.execute_calls == []      # soft_delete 없음
    assert conn.closed is True


async def test_seed_us_empty_response_skips_soft_delete(monkeypatch):
    """빈 응답(rows=[]) → soft_delete 미호출(대량 오상폐 방지) + upsert 미호출."""
    conn = _SeedUsConn(lock_acquired=True)
    _patch_seed_us(monkeypatch, conn, [])

    await stock_seed.seed_us("postgresql://x")

    assert conn.executemany_calls == []  # upsert 없음
    assert conn.execute_calls == []      # soft_delete 없음(빈응답 가드)
    assert conn.closed is True


def _async_return(value):
    async def _coro():
        return value
    return _coro()
