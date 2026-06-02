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


async def test_fetch_stock_prices_parses_ticker_and_marcap():
    def handler(req: httpx.Request) -> httpx.Response:
        # 첫 후보 basDt 에서 바로 응답.
        return httpx.Response(
            200,
            json=_body(
                [
                    {"srtnCd": "A005930", "mrktTotAmt": "400000000000000"},
                    {"srtnCd": "000660", "mrktTotAmt": "90000000000000"},
                ]
            ),
        )

    async with _mock_client(handler) as client:
        rows = await stock_seed.fetch_stock_prices("key", client=client)

    assert {r["ticker"]: r["marcap"] for r in rows} == {
        "005930": 400000000000000,
        "000660": 90000000000000,
    }
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
    assert rows[-1] == {"ticker": "999999", "marcap": 2000, "bas_dt": rows[-1]["bas_dt"]}


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

    assert rows == [{"ticker": "005930", "marcap": 100, "bas_dt": rows[0]["bas_dt"]}]


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
