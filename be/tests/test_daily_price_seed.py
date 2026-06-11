"""daily_price_seed.fetch_daily_closes 테스트 — getStockPriceInfo 범위 조회 mock.

실측 응답 shape(basDt/clpr/srtnCd 6자리) httpx mock 으로 검증.
srtnCd 정확 일치 필터(likeSrtnCd 부분일치 혼입 방지) · clpr 파싱 · 범위 params 전달 · 페이징.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import httpx

from invest_note_api.services import daily_price_seed


def _body(items: list[dict]) -> dict:
    return {"response": {"body": {"items": {"item": items}}}}


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_daily_closes_parses_basdt_clpr():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(
                [
                    {"srtnCd": "005930", "basDt": "20250602", "clpr": "75000", "itmsNm": "삼성전자"},
                    {"srtnCd": "005930", "basDt": "20250603", "clpr": "76100", "itmsNm": "삼성전자"},
                ]
            ),
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_daily_closes(
            "key", "005930", date(2025, 6, 2), date(2025, 6, 3), client=client
        )

    assert rows == [
        {"ticker": "005930", "close_date": date(2025, 6, 2), "close_price": 75000.0},
        {"ticker": "005930", "close_date": date(2025, 6, 3), "close_price": 76100.0},
    ]


async def test_fetch_daily_closes_filters_partial_srtncd_match():
    """likeSrtnCd 는 부분일치라 다른 종목(005935 등)이 섞여올 수 있다 → 정확 일치만 채택."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(
                [
                    {"srtnCd": "005930", "basDt": "20250602", "clpr": "75000"},
                    {"srtnCd": "005935", "basDt": "20250602", "clpr": "61000"},  # 우선주 혼입
                    {"srtnCd": "A005930", "basDt": "20250603", "clpr": "76100"},  # 'A' 접두 정규화
                ]
            ),
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_daily_closes(
            "key", "005930", date(2025, 6, 2), date(2025, 6, 3), client=client
        )

    tickers = {r["ticker"] for r in rows}
    assert tickers == {"005930"}
    assert len(rows) == 2  # 005935 제외, A005930 은 정규화로 채택.


async def test_fetch_daily_closes_passes_range_params():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(dict(req.url.params))
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        await daily_price_seed.fetch_daily_closes(
            "mykey", "005930", date(2025, 1, 2), date(2025, 6, 3), client=client
        )

    assert captured["likeSrtnCd"] == "005930"
    assert captured["beginBasDt"] == "20250102"
    assert captured["endBasDt"] == "20250603"
    assert captured["resultType"] == "json"
    assert captured["serviceKey"] == "mykey"


async def test_fetch_daily_closes_pages_through_full_pages():
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params["pageNo"])
        calls.append(page)
        if page == 1:
            items = [
                {"srtnCd": "005930", "basDt": f"2025{m:02d}01", "clpr": "1000"}
                for m in range(1, daily_price_seed._PAGE_SIZE + 1)
            ]
            return httpx.Response(200, json=_body(items))
        return httpx.Response(
            200, json=_body([{"srtnCd": "005930", "basDt": "20251231", "clpr": "2000"}])
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_daily_closes(
            "key", "005930", date(2025, 1, 1), date(2025, 12, 31), client=client
        )

    assert calls[:2] == [1, 2]
    assert rows[-1]["close_price"] == 2000.0


# ─────────────────────────── admin: POST /admin/seed/daily-prices ───────────────────────────


def _admin_client(admin_token: str):
    from fastapi.testclient import TestClient

    from invest_note_api.config import Settings, get_settings
    from invest_note_api.main import create_app

    settings = Settings(supabase_url="https://test.supabase.co", admin_token=admin_token)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_admin_seed_daily_prices_rejects_missing_token():
    client = _admin_client("secret")
    r = client.post("/admin/seed/daily-prices")
    assert r.status_code == 403


def test_admin_seed_daily_prices_accepts_valid_token_returns_202(monkeypatch):
    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr("invest_note_api.routers.admin.run_seed_daily_prices", noop)
    client = _admin_client("secret")
    r = client.post("/admin/seed/daily-prices", headers={"X-Admin-Token": "secret"})
    assert r.status_code == 202
    assert r.json() == {"status": "started"}


# ─────────────────────────── ETF/ETN 엔드포인트 라우팅 ───────────────────────────


def test_price_url_for_market_routes_etf_etn():
    assert daily_price_seed._price_url_for_market("ETF") == daily_price_seed._ETF_PRICE_URL
    assert daily_price_seed._price_url_for_market("ETN") == daily_price_seed._ETN_PRICE_URL
    assert daily_price_seed._price_url_for_market("KOSPI") == daily_price_seed._STOCK_PRICE_URL
    assert daily_price_seed._price_url_for_market(None) == daily_price_seed._STOCK_PRICE_URL


async def test_fetch_daily_closes_uses_given_url():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["path"] = req.url.path
        return httpx.Response(200, json=_body([]))

    async with _mock_client(handler) as client:
        await daily_price_seed.fetch_daily_closes(
            "key", "360750", date(2025, 1, 1), date(2025, 6, 1),
            url=daily_price_seed._ETF_PRICE_URL, client=client,
        )

    assert captured["path"].endswith("/getETFPriceInfo")


def _fake_conn(markets: dict[str, str]):
    """market 조회(conn.fetch)만 흉내내는 FakeConn. repo 함수는 테스트에서 monkeypatch."""

    class FakeConn:
        async def fetch(self, q, *args):
            return [{"ticker": tk, "market": mk} for tk, mk in markets.items()]

    return FakeConn()


def _patch_repo(
    monkeypatch,
    *,
    watermarks: dict | None = None,
    sync_state: dict | None = None,
    fetch_fn=None,
    naver_fn=None,
):
    """backfill_closes 의 repo 의존성을 monkeypatch 하고, 호출 추적 dict 를 돌려준다."""
    from invest_note_api.db_ops import daily_prices_repo

    track: dict = {"fetched": [], "upserted_closes": [], "sync_rows": [], "naver_fetched": []}

    async def fake_watermarks(conn, tickers, **kw):
        return watermarks or {}

    async def fake_sync_state(conn, tickers, **kw):
        return sync_state or {}

    async def fake_upsert_closes(conn, rows, **kw):
        track["upserted_closes"].extend(rows)
        return len(rows)

    async def fake_upsert_sync(conn, rows, **kw):
        track["sync_rows"].extend(rows)
        return len(rows)

    async def default_fetch(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        track["fetched"].append((ticker, begin, end, url))
        return []

    async def default_naver(client, ticker, begin, end):
        track["naver_fetched"].append((ticker, begin, end))
        return []

    monkeypatch.setattr(daily_prices_repo, "get_watermarks", fake_watermarks)
    monkeypatch.setattr(daily_prices_repo, "get_sync_state", fake_sync_state)
    monkeypatch.setattr(daily_prices_repo, "upsert_closes", fake_upsert_closes)
    monkeypatch.setattr(daily_prices_repo, "upsert_sync_state", fake_upsert_sync)
    monkeypatch.setattr(daily_price_seed, "fetch_daily_closes", fetch_fn or default_fetch)
    monkeypatch.setattr(daily_price_seed, "fetch_naver_daily_closes", naver_fn or default_naver)
    return track


async def test_backfill_routes_endpoint_by_market(monkeypatch):
    """ETF/ETN 보유 종목은 증권상품시세, 주식은 주식시세 엔드포인트로 라우팅."""
    track = _patch_repo(monkeypatch)
    conn = _fake_conn({"360750": "ETF", "500001": "ETN", "005930": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["360750", "500001", "005930"], date(2024, 1, 1), date(2026, 1, 1)
    )

    url_of = {tk: url for tk, _b, _e, url in track["fetched"]}
    assert url_of["360750"] == daily_price_seed._ETF_PRICE_URL
    assert url_of["500001"] == daily_price_seed._ETN_PRICE_URL
    assert url_of["005930"] == daily_price_seed._STOCK_PRICE_URL


async def test_backfill_skips_recently_checked_empty_range(monkeypatch):
    """어제까지 최근 확인(빈 범위)한 종목은 쿨다운 내 data.go.kr 재질의 안 함."""
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)
    track = _patch_repo(
        monkeypatch,
        watermarks={"005930": date(2026, 6, 2)},  # 마지막 거래일 < 어제(휴장)
        sync_state={
            "005930": {
                "checked_through_date": yesterday,
                "checked_at": datetime.now(timezone.utc),  # 방금 확인 → 쿨다운 내
            }
        },
    )
    conn = _fake_conn({"005930": "KOSPI"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    assert track["fetched"] == []  # 호출 없음
    assert incomplete is False


async def test_backfill_reprobes_after_cooldown(monkeypatch):
    """checked_at 이 쿨다운을 지났으면 빈 범위라도 1회 재probe(늦은 발행 대응)."""
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)
    stale = datetime.now(timezone.utc) - (daily_price_seed._BACKFILL_RECHECK_COOLDOWN + timedelta(hours=1))
    track = _patch_repo(
        monkeypatch,
        watermarks={"005930": date(2026, 6, 2)},
        sync_state={"005930": {"checked_through_date": yesterday, "checked_at": stale}},
    )
    conn = _fake_conn({"005930": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    assert [tk for tk, *_ in track["fetched"]] == ["005930"]  # 재probe 1회
    # 빈 응답이어도 sync_state 갱신(checked_through = 어제).
    assert track["sync_rows"] == [{"ticker": "005930", "checked_through_date": yesterday}]


async def test_backfill_fetches_new_ticker_once_and_marks(monkeypatch):
    """watermark/sync_state 없는 신규 종목은 1회 fetch 후 checked_through 기록."""
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})
    conn = _fake_conn({"123456": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["123456"], date(2026, 6, 1), today
    )

    assert [tk for tk, *_ in track["fetched"]] == ["123456"]
    assert track["sync_rows"] == [{"ticker": "123456", "checked_through_date": yesterday}]


async def test_backfill_upserts_all_tickers_in_single_batch(monkeypatch):
    """여러 종목 rows 는 한 번의 upsert_closes 배치로 적재된다(왕복 N→1)."""
    from invest_note_api.db_ops import daily_prices_repo

    today = date(2026, 6, 4)

    async def fetch_rows(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        return [{"ticker": ticker, "close_date": date(2026, 6, 3), "close_price": 100.0}]

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=fetch_rows)
    calls = {"n": 0}
    orig_upsert = daily_prices_repo.upsert_closes

    async def counting_upsert(conn, rows, **kw):
        calls["n"] += 1
        return await orig_upsert(conn, rows, **kw)

    monkeypatch.setattr(daily_prices_repo, "upsert_closes", counting_upsert)
    conn = _fake_conn({"005930": "KOSPI", "000660": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["005930", "000660"], date(2026, 6, 1), today
    )

    assert calls["n"] == 1  # 단일 배치.
    assert {r["ticker"] for r in track["upserted_closes"]} == {"005930", "000660"}


async def test_backfill_fetch_exception_keeps_state_unrecorded(monkeypatch):
    """fetch 예외 종목은 sync_state 미기록 + incomplete=True(다음 요청 재시도 보장)."""
    today = date(2026, 6, 4)

    async def boom(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        raise RuntimeError("gateway down")

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=boom)
    conn = _fake_conn({"005930": "KOSPI"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    assert incomplete is True
    assert track["sync_rows"] == []  # 실패 종목 상태 미기록


async def test_backfill_fetches_in_parallel_within_limit(monkeypatch):
    """여러 종목 fetch 는 동시 실행되며 동시성은 _BACKFILL_CONCURRENCY 로 제한된다."""
    today = date(2026, 6, 4)
    state = {"current": 0, "peak": 0}

    async def slow_fetch(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        state["current"] += 1
        state["peak"] = max(state["peak"], state["current"])
        await asyncio.sleep(0.02)
        state["current"] -= 1
        return []

    n = daily_price_seed._BACKFILL_CONCURRENCY + 4
    tickers = [f"{i:06d}" for i in range(n)]
    _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=slow_fetch)
    conn = _fake_conn({tk: "KOSPI" for tk in tickers})

    await daily_price_seed.backfill_closes(
        conn, "key", tickers, date(2026, 6, 1), today
    )

    assert state["peak"] > 1  # 실제로 병렬 실행됨(순차였다면 peak=1)
    assert state["peak"] <= daily_price_seed._BACKFILL_CONCURRENCY  # 상한 준수


# ─────────────────────────── 네이버 tail-gap 보충 ───────────────────────────


async def test_fetch_naver_daily_closes_parses_localdate_closeprice():
    """실측 응답 shape(localDate/closePrice) 파싱 + 범위 params 전달."""
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["path"] = req.url.path
        captured.update(dict(req.url.params))
        return httpx.Response(
            200,
            json=[
                {"localDate": "20260604", "closePrice": 351500.0, "openPrice": 349000.0},
                {"localDate": "20260605", "closePrice": 329000.0, "openPrice": 333500.0},
            ],
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_naver_daily_closes(
            client, "005930", date(2026, 6, 4), date(2026, 6, 5)
        )

    assert captured["path"] == "/chart/domestic/item/005930/day"
    assert captured["startDateTime"] == "20260604000000"
    assert captured["endDateTime"] == "20260605000000"
    assert rows == [
        {"ticker": "005930", "close_date": date(2026, 6, 4), "close_price": 351500.0},
        {"ticker": "005930", "close_date": date(2026, 6, 5), "close_price": 329000.0},
    ]


async def test_fetch_naver_daily_closes_skips_bad_and_out_of_range_items():
    """결측/파싱불가/범위 밖 행 skip — 범위 밖 종가가 watermark 를 오염시키지 않게."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"localDate": "20260605", "closePrice": 329000.0},
                {"localDate": "20260606", "closePrice": 999.0},  # 범위 밖(end 초과)
                {"localDate": "", "closePrice": 100.0},  # 날짜 결측
                {"localDate": "20260605", "closePrice": None},  # 종가 결측
            ],
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_naver_daily_closes(
            client, "005930", date(2026, 6, 5), date(2026, 6, 5)
        )

    assert rows == [
        {"ticker": "005930", "close_date": date(2026, 6, 5), "close_price": 329000.0},
    ]


async def test_fetch_naver_daily_closes_non_list_response_returns_empty():
    """미지원 종목(ETN 등) 오류 객체 응답 → 빈 배열(보충 없음)."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "StockConflict"})

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_naver_daily_closes(
            client, "580011", date(2026, 6, 5), date(2026, 6, 5)
        )

    assert rows == []


async def test_backfill_naver_fills_tail_gap(monkeypatch):
    """data.go.kr 가 어제 전날까지만 발행(T+1) → 공백(어제)만 네이버로 보충해 함께 upsert."""
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)

    async def datagokr_through_0602(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        return [{"ticker": ticker, "close_date": date(2026, 6, 2), "close_price": 100.0}]

    async def naver_0603(client, ticker, begin, end):
        track["naver_fetched"].append((ticker, begin, end))
        return [{"ticker": ticker, "close_date": date(2026, 6, 3), "close_price": 110.0}]

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=datagokr_through_0602, naver_fn=naver_0603)
    conn = _fake_conn({"005930": "KOSPI"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    # 공백 구간(6/3~6/3)만 네이버 질의.
    assert track["naver_fetched"] == [("005930", date(2026, 6, 3), date(2026, 6, 3))]
    assert {r["close_date"] for r in track["upserted_closes"]} == {date(2026, 6, 2), date(2026, 6, 3)}
    assert track["sync_rows"] == [{"ticker": "005930", "checked_through_date": yesterday}]
    assert incomplete is False


async def test_backfill_gap_provider_none_disables_naver(monkeypatch):
    """gap_provider="none" → 공백 구간이 있어도 네이버 보충 미호출(env 비활성 토글)."""
    today = date(2026, 6, 4)

    async def datagokr_through_0602(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        return [{"ticker": ticker, "close_date": date(2026, 6, 2), "close_price": 100.0}]

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=datagokr_through_0602)
    conn = _fake_conn({"005930": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today, gap_provider="none"
    )

    assert track["naver_fetched"] == []  # 보충 비활성 — primary 분만 upsert.
    assert [r["close_date"] for r in track["upserted_closes"]] == [date(2026, 6, 2)]


async def test_backfill_unknown_provider_raises_value_error(monkeypatch):
    """registry 에 없는 공급자명(env 오타) → ValueError fail-fast."""
    import pytest

    track = _patch_repo(monkeypatch)
    conn = _fake_conn({"005930": "KOSPI"})

    with pytest.raises(ValueError, match="daily_price"):
        await daily_price_seed.backfill_closes(
            conn, "key", ["005930"], date(2026, 6, 1), date(2026, 6, 4), primary_provider="kisss"
        )
    assert track["fetched"] == []


def test_validate_daily_price_providers_startup_fail_fast():
    """env 오타가 /assets/history 요청 500 으로 미루어지지 않게 부팅 시점 검증(lifespan 호출)."""
    import pytest

    daily_price_seed.validate_daily_price_providers("data_go_kr", "naver")
    daily_price_seed.validate_daily_price_providers("kis", "none")  # gap 비활성 값 허용
    daily_price_seed.validate_daily_price_providers("kis", "")
    with pytest.raises(ValueError, match="daily_price"):
        daily_price_seed.validate_daily_price_providers("kisss", "naver")
    with pytest.raises(ValueError, match="daily_price_gap"):
        daily_price_seed.validate_daily_price_providers("data_go_kr", "navr")


async def test_backfill_naver_failure_keeps_datagokr_rows_state_unrecorded(monkeypatch):
    """네이버 보충 실패 → data.go.kr 분은 upsert, sync_state 미기록 + incomplete(재시도 보장)."""
    today = date(2026, 6, 4)

    async def datagokr_through_0602(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        return [{"ticker": ticker, "close_date": date(2026, 6, 2), "close_price": 100.0}]

    async def naver_boom(client, ticker, begin, end):
        raise RuntimeError("naver down")

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=datagokr_through_0602, naver_fn=naver_boom)
    conn = _fake_conn({"005930": "KOSPI"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    assert [r["close_date"] for r in track["upserted_closes"]] == [date(2026, 6, 2)]
    assert track["sync_rows"] == []  # 미기록 → 쿨다운 없이 다음 요청 재시도.
    assert incomplete is True


async def test_backfill_naver_not_called_when_filled_through_yesterday(monkeypatch):
    """data.go.kr 가 어제까지 채움(발행 완료) → 네이버 미호출."""
    today = date(2026, 6, 4)

    async def datagokr_through_yesterday(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        return [{"ticker": ticker, "close_date": date(2026, 6, 3), "close_price": 100.0}]

    track = _patch_repo(monkeypatch, watermarks={}, sync_state={}, fetch_fn=datagokr_through_yesterday)
    conn = _fake_conn({"005930": "KOSPI"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["005930"], date(2026, 6, 1), today
    )

    assert track["naver_fetched"] == []


async def test_backfill_naver_not_called_for_non_kr(monkeypatch):
    """KR 외 country 는 네이버 domestic 경로 미지원 → 보충 skip."""
    today = date(2026, 6, 4)
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})

    async def yahoo_rows(client, ticker, begin, end):
        return [{"ticker": ticker, "close_date": date(2026, 6, 3), "close_price": 190.0}]

    monkeypatch.setattr(daily_price_seed, "_fetch_yahoo_us_closes", yahoo_rows)
    conn = _fake_conn({"AAPL": "STOCK"})

    await daily_price_seed.backfill_closes(
        conn, "key", ["AAPL"], date(2026, 6, 1), today, country_code="US"
    )

    assert track["naver_fetched"] == []


# ─────────────────────────── US backfill 라우팅 (D1-2) ───────────────────────────


async def test_backfill_us_routes_to_yahoo_and_records_state(monkeypatch):
    """country_code=US 는 env primary 우회 → _fetch_yahoo_us_closes 로 upsert + sync_state 기록.

    api_key="" 로 호출해 키 가드 우회와 Yahoo 라우팅을 한 테스트로 검증.
    """
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})

    called: list[tuple] = []

    async def yahoo_rows(client, ticker, begin, end):
        called.append((ticker, begin, end))
        return [{"ticker": ticker, "close_date": yesterday, "close_price": 190.5}]

    monkeypatch.setattr(daily_price_seed, "_fetch_yahoo_us_closes", yahoo_rows)
    conn = _fake_conn({"AAPL": "STOCK"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "", ["AAPL"], date(2026, 6, 1), today, country_code="US"
    )

    assert [tk for tk, *_ in called] == ["AAPL"]  # data.go.kr 경로 미사용
    assert track["fetched"] == []  # fetch_daily_closes(KR primary) 미호출
    assert track["upserted_closes"] == [
        {"ticker": "AAPL", "close_date": yesterday, "close_price": 190.5}
    ]
    assert track["sync_rows"] == [{"ticker": "AAPL", "checked_through_date": yesterday}]
    assert incomplete is False


async def test_backfill_us_empty_response_records_state(monkeypatch):
    """정상 200 의 빈 범위(주말/휴장)는 synced 처리 — 쿨다운으로 재질의 폭주 방지.

    빈 결과를 실패로 승격하면 주말마다 매 요청 Yahoo 재호출 + incomplete 배너가 상시 노출되므로,
    전송 실패(raise)와 구분해 KR data.go.kr 의 빈 응답 synced 처리와 대칭으로 둔다.
    """
    today = date(2026, 6, 4)
    yesterday = date(2026, 6, 3)
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})

    async def yahoo_empty(client, ticker, begin, end):
        return []

    monkeypatch.setattr(daily_price_seed, "_fetch_yahoo_us_closes", yahoo_empty)
    conn = _fake_conn({"AAPL": "STOCK"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "", ["AAPL"], date(2026, 6, 1), today, country_code="US"
    )

    assert track["upserted_closes"] == []
    # 과거 fixture 라 cutoff(현재 시각 기준) > yesterday → 클램프 없이 yesterday 기록.
    assert track["sync_rows"] == [{"ticker": "AAPL", "checked_through_date": yesterday}]
    assert incomplete is False


async def test_backfill_us_fetch_failure_keeps_state_unrecorded(monkeypatch):
    """전송 실패(예외/비200)는 sync_state 미advance + incomplete — 다음 요청 재시도 보장."""
    today = date(2026, 6, 4)
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})

    async def yahoo_fail(client, ticker, begin, end):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(daily_price_seed, "_fetch_yahoo_us_closes", yahoo_fail)
    conn = _fake_conn({"AAPL": "STOCK"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "", ["AAPL"], date(2026, 6, 1), today, country_code="US"
    )

    assert track["upserted_closes"] == []
    assert track["sync_rows"] == []  # sync_state 미기록 → 쿨다운 advance 안 함
    assert incomplete is True


async def test_backfill_us_clamps_checked_through_to_cutoff(monkeypatch):
    """새벽(미장 진행 중)에는 checked_through 를 cutoff 로 클램프 — 확정 종가 적재 지연 방지.

    yesterday 로 박으면 cooldown 동안 (장 마감 후 확정된) yesterday 종가 적재가 늦어진다.
    """
    today = date(2026, 6, 4)
    cutoff = date(2026, 6, 2)  # yesterday(6/3) 미확정인 새벽 시각 가정
    track = _patch_repo(monkeypatch, watermarks={}, sync_state={})

    async def yahoo_rows(client, ticker, begin, end):
        return [{"ticker": ticker, "close_date": cutoff, "close_price": 190.5}]

    monkeypatch.setattr(daily_price_seed, "_fetch_yahoo_us_closes", yahoo_rows)
    monkeypatch.setattr(daily_price_seed, "_us_final_close_cutoff", lambda now: cutoff)
    conn = _fake_conn({"AAPL": "STOCK"})

    incomplete = await daily_price_seed.backfill_closes(
        conn, "", ["AAPL"], date(2026, 6, 1), today, country_code="US"
    )

    assert track["sync_rows"] == [{"ticker": "AAPL", "checked_through_date": cutoff}]
    assert incomplete is False


async def test_fetch_daily_closes_skips_missing_clpr():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(
                [
                    {"srtnCd": "005930", "basDt": "20250602", "clpr": ""},
                    {"srtnCd": "005930", "basDt": "20250603", "clpr": "76100"},
                ]
            ),
        )

    async with _mock_client(handler) as client:
        rows = await daily_price_seed.fetch_daily_closes(
            "key", "005930", date(2025, 6, 2), date(2025, 6, 3), client=client
        )

    assert len(rows) == 1
    assert rows[0]["close_price"] == 76100.0


# ─────────────────────────── KIS 기간별 시세 ───────────────────────────

KIS_BASE = "https://openapi.koreainvestment.com:9443"


def _kis_state(monkeypatch):
    from invest_note_api.external import kis

    monkeypatch.setattr(kis, "_state", kis.KisState(app_key="key", app_secret="secret"))


def _kis_handler(pages: list[list[dict]], captured: list[dict]):
    """차트 호출마다 pages 를 순서대로 반환. tokenP 는 항상 성공."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 86400})
        captured.append(dict(req.url.params))
        idx = len(captured) - 1
        output2 = pages[idx] if idx < len(pages) else []
        return httpx.Response(200, json={"rt_cd": "0", "output2": output2})

    return handler


async def test_fetch_kis_daily_closes_parses_and_sends_params(monkeypatch):
    """output2(stck_bsop_date/stck_clpr) 파싱 + FID 파라미터 전달 검증."""
    _kis_state(monkeypatch)
    captured: list[dict] = []
    pages = [
        [
            {"stck_bsop_date": "20260603", "stck_clpr": "71000"},
            {"stck_bsop_date": "20260602", "stck_clpr": "70500"},
        ]
    ]

    async with _mock_client(_kis_handler(pages, captured)) as client:
        rows = await daily_price_seed.fetch_kis_daily_closes(
            client, "005930", date(2026, 6, 2), date(2026, 6, 3)
        )

    assert captured[0]["FID_INPUT_ISCD"] == "005930"
    assert captured[0]["FID_INPUT_DATE_1"] == "20260602"
    assert captured[0]["FID_INPUT_DATE_2"] == "20260603"
    assert captured[0]["FID_PERIOD_DIV_CODE"] == "D"
    assert captured[0]["FID_ORG_ADJ_PRC"] == "1"
    assert rows == [
        {"ticker": "005930", "close_date": date(2026, 6, 3), "close_price": 71000.0},
        {"ticker": "005930", "close_date": date(2026, 6, 2), "close_price": 70500.0},
    ]


async def test_fetch_kis_daily_closes_pages_with_end_cursor(monkeypatch):
    """100건 상한 — 가장 오래된 행 직전일로 end 커서를 당겨 추가 호출."""
    _kis_state(monkeypatch)
    captured: list[dict] = []
    pages = [
        [{"stck_bsop_date": "20260603", "stck_clpr": "71000"},
         {"stck_bsop_date": "20260602", "stck_clpr": "70500"}],
        [{"stck_bsop_date": "20260601", "stck_clpr": "70000"}],
    ]

    async with _mock_client(_kis_handler(pages, captured)) as client:
        rows = await daily_price_seed.fetch_kis_daily_closes(
            client, "005930", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert len(captured) == 2
    assert captured[1]["FID_INPUT_DATE_2"] == "20260601"  # oldest(6/2) - 1일
    assert {r["close_date"] for r in rows} == {date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)}


async def test_fetch_kis_daily_closes_empty_page_stops(monkeypatch):
    """빈 output2(휴장/상장 전) → 추가 페이징 없이 종료."""
    _kis_state(monkeypatch)
    captured: list[dict] = []

    async with _mock_client(_kis_handler([[]], captured)) as client:
        rows = await daily_price_seed.fetch_kis_daily_closes(
            client, "005930", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert rows == []
    assert len(captured) == 1


async def test_fetch_kis_daily_closes_error_raises(monkeypatch):
    """오류 응답(rt_cd!=0) → 예외. primary 계약상 실패는 raise 해야 sync_state 미기록."""
    import pytest

    _kis_state(monkeypatch)

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 86400})
        return httpx.Response(200, json={"rt_cd": "1", "msg_cd": "EGW00121", "msg1": "err"})

    async with _mock_client(handler) as client:
        with pytest.raises(RuntimeError, match="KIS"):
            await daily_price_seed.fetch_kis_daily_closes(
                client, "005930", date(2026, 6, 1), date(2026, 6, 3)
            )


# ─────────────────────────── Yahoo US 일별 종가(D1-1) ───────────────────────────
# US 종목은 bare 티커 + Yahoo chart v8 timestamp[]+close[] 시계열. epoch(UTC)→KST date.
# 미국장 개장 13:30 UTC 를 사용해 UTC→KST .date() 변환을 실제로 행사한다(자정이면 trivial).

def _yahoo_us_body(ticker: str, points: list[tuple[int, float | None]]) -> dict:
    """points: [(epoch_sec, close|None)] → Yahoo chart v8 result shape."""
    return {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": ticker, "currency": "USD"},
                    "timestamp": [ts for ts, _ in points],
                    "indicators": {"quote": [{"close": [c for _, c in points]}]},
                }
            ],
            "error": None,
        }
    }


def _us_epoch(d: date) -> int:
    """해당 날짜 미국장 개장(13:30 UTC) epoch — KST 로 변환해도 같은 날짜."""
    return int(datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc).timestamp())


async def test_fetch_yahoo_us_closes_parses_timestamp_close():
    """timestamp[]+close[] → [{ticker, close_date, close_price}], bare 티커 유지(정규화 안 함)."""
    points = [
        (_us_epoch(date(2026, 6, 1)), 201.5),
        (_us_epoch(date(2026, 6, 2)), 203.0),
        (_us_epoch(date(2026, 6, 3)), 205.25),
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_yahoo_us_body("AAPL", points))

    async with _mock_client(handler) as client:
        rows = await daily_price_seed._fetch_yahoo_us_closes(
            client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert rows == [
        {"ticker": "AAPL", "close_date": date(2026, 6, 1), "close_price": 201.5},
        {"ticker": "AAPL", "close_date": date(2026, 6, 2), "close_price": 203.0},
        {"ticker": "AAPL", "close_date": date(2026, 6, 3), "close_price": 205.25},
    ]
    # bare 티커 유지 — _normalize_ticker('AAPL') 의 garbage('PL') 가 아님.
    assert {r["ticker"] for r in rows} == {"AAPL"}


async def test_fetch_yahoo_us_closes_skips_null_close():
    """null close(휴장/미체결 캔들)는 스킵, 나머지는 채택."""
    points = [
        (_us_epoch(date(2026, 6, 1)), 201.5),
        (_us_epoch(date(2026, 6, 2)), None),
        (_us_epoch(date(2026, 6, 3)), 205.25),
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_yahoo_us_body("AAPL", points))

    async with _mock_client(handler) as client:
        rows = await daily_price_seed._fetch_yahoo_us_closes(
            client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert [r["close_date"] for r in rows] == [date(2026, 6, 1), date(2026, 6, 3)]


async def test_fetch_yahoo_us_closes_drops_out_of_range_rows():
    """범위 밖(경계일 라이브 캔들 등)은 begin~end 가드로 제외."""
    points = [
        (_us_epoch(date(2026, 5, 30)), 199.0),  # begin 이전
        (_us_epoch(date(2026, 6, 1)), 201.5),
        (_us_epoch(date(2026, 6, 4)), 210.0),  # end 이후
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_yahoo_us_body("AAPL", points))

    async with _mock_client(handler) as client:
        rows = await daily_price_seed._fetch_yahoo_us_closes(
            client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert rows == [
        {"ticker": "AAPL", "close_date": date(2026, 6, 1), "close_price": 201.5},
    ]


async def test_fetch_yahoo_us_closes_sends_period_params_and_bare_symbol():
    """period1/period2(UTC epoch sec) params 전달 + period2 가 end 다음날 자정(end 포함)."""
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["params"] = dict(req.url.params)
        return httpx.Response(200, json=_yahoo_us_body("AAPL", []))

    begin, end = date(2026, 6, 1), date(2026, 6, 3)
    async with _mock_client(handler) as client:
        await daily_price_seed._fetch_yahoo_us_closes(client, "AAPL", begin, end)

    # bare 티커 — suffix(.KS/.KQ) 없음.
    assert "/chart/AAPL" in captured["url"]
    expect_p1 = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    expect_p2 = int(datetime(2026, 6, 4, tzinfo=timezone.utc).timestamp())  # end+1일
    assert int(captured["params"]["period1"]) == expect_p1
    assert int(captured["params"]["period2"]) == expect_p2
    assert captured["params"]["interval"] == "1d"


async def test_fetch_yahoo_us_closes_converts_preferred_symbol_in_url():
    """우선주 seed 표기 BAC$B 입력 → Yahoo URL 은 변환된 BAC-PB(원본 미전송)."""
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=_yahoo_us_body("BAC-PB", []))

    async with _mock_client(handler) as client:
        await daily_price_seed._fetch_yahoo_us_closes(
            client, "BAC$B", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert "/chart/BAC-PB" in captured["url"]
    assert "BAC$B" not in captured["url"]
    assert "%24" not in captured["url"]  # `$` URL-encode 형태도 미전송


async def test_fetch_yahoo_us_closes_includes_end_day_candle():
    """end 당일 캔들이 결과에 포함되는지(period2 inclusive 회귀)."""
    points = [(_us_epoch(date(2026, 6, 3)), 205.25)]

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_yahoo_us_body("AAPL", points))

    async with _mock_client(handler) as client:
        rows = await daily_price_seed._fetch_yahoo_us_closes(
            client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert rows == [
        {"ticker": "AAPL", "close_date": date(2026, 6, 3), "close_price": 205.25},
    ]


async def test_fetch_yahoo_us_closes_empty_result_returns_empty():
    """result 없음(빈 chart) → 빈 리스트."""
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"chart": {"result": [], "error": None}})

    async with _mock_client(handler) as client:
        rows = await daily_price_seed._fetch_yahoo_us_closes(
            client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
        )

    assert rows == []


async def test_fetch_yahoo_us_closes_failure_raises():
    """비200(404 등) 실패는 raise 전파 — backfill 이 sync_state 미기록(재시도 보장).

    정상 200 의 빈 범위([])와 구분한다 — 빈 결과를 실패로 승격하면 주말마다 재질의가 폭주한다.
    """
    import pytest

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})

    async with _mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await daily_price_seed._fetch_yahoo_us_closes(
                client, "AAPL", date(2026, 6, 1), date(2026, 6, 3)
            )


async def test_fetch_yahoo_us_closes_rejects_path_manipulating_ticker():
    """화이트리스트 위반 ticker(`/`·`?` 등)는 HTTP 전송 없이 raise — fetch 실패 계약 일관."""
    import pytest

    called = {"hit": False}

    def handler(_req: httpx.Request) -> httpx.Response:
        called["hit"] = True
        return httpx.Response(200, json={"chart": {"result": []}})

    async with _mock_client(handler) as client:
        for bad in ("AAPL/../foo", "AAPL?x=1", "AAPL#frag", ""):
            with pytest.raises(ValueError):
                await daily_price_seed._fetch_yahoo_us_closes(
                    client, bad, date(2026, 6, 1), date(2026, 6, 3)
                )
    assert called["hit"] is False, "위반 ticker 인데 HTTP 요청이 전송됨"


def test_us_final_close_cutoff_overnight_window():
    """캔들 날짜 D 는 now >= D+1 07:00 KST 일 때만 확정 — 새벽엔 D-1 까지만."""
    from invest_note_api.domain.trade_utils import KST

    d = date(2026, 6, 3)
    # D+1 02:00 KST — 미장(D 세션) 진행 중 → D 미확정, cutoff = D-1
    now_night = datetime(2026, 6, 4, 2, 0, tzinfo=KST)
    assert daily_price_seed._us_final_close_cutoff(now_night) == d - timedelta(days=1)
    # D+1 08:00 KST — 마감(05/06:00) + 버퍼 경과 → D 확정
    now_morning = datetime(2026, 6, 4, 8, 0, tzinfo=KST)
    assert daily_price_seed._us_final_close_cutoff(now_morning) == d


def test_parse_yahoo_us_chart_cutoff_drops_unconfirmed_candle():
    """cutoff(미확정 경계) 초과 캔들은 범위 내(<=end)여도 제외 — 장중 라이브가 박제 방지."""
    points = [
        (_us_epoch(date(2026, 6, 2)), 203.0),
        (_us_epoch(date(2026, 6, 3)), 205.25),  # end 이내지만 cutoff(6/2) 초과 → drop
    ]
    rows = daily_price_seed._parse_yahoo_us_chart(
        _yahoo_us_body("AAPL", points),
        "AAPL",
        date(2026, 6, 1),
        date(2026, 6, 3),
        cutoff=date(2026, 6, 2),
    )
    assert rows == [
        {"ticker": "AAPL", "close_date": date(2026, 6, 2), "close_price": 203.0},
    ]
