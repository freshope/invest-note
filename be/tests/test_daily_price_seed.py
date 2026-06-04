"""daily_price_seed.fetch_daily_closes 테스트 — getStockPriceInfo 범위 조회 mock.

실측 응답 shape(basDt/clpr/srtnCd 6자리) httpx mock 으로 검증.
srtnCd 정확 일치 필터(likeSrtnCd 부분일치 혼입 방지) · clpr 파싱 · 범위 params 전달 · 페이징.
"""
from __future__ import annotations

from datetime import date

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


async def test_backfill_routes_endpoint_by_market(monkeypatch):
    """ETF/ETN 보유 종목은 증권상품시세, 주식은 주식시세 엔드포인트로 라우팅."""
    from invest_note_api.db_ops import daily_prices_repo

    async def fake_watermarks(conn, tickers, **kw):
        return {}

    async def fake_upsert(conn, rows, **kw):
        return len(rows)

    monkeypatch.setattr(daily_prices_repo, "get_watermarks", fake_watermarks)
    monkeypatch.setattr(daily_prices_repo, "upsert_closes", fake_upsert)

    calls: list[tuple[str, str]] = []

    async def fake_fetch(api_key, ticker, begin, end, *, url=daily_price_seed._STOCK_PRICE_URL, client=None):
        calls.append((ticker, url))
        return []

    monkeypatch.setattr(daily_price_seed, "fetch_daily_closes", fake_fetch)

    class FakeConn:
        async def fetch(self, q, *args):
            return [
                {"ticker": "360750", "market": "ETF"},
                {"ticker": "500001", "market": "ETN"},
                {"ticker": "005930", "market": "KOSPI"},
            ]

    await daily_price_seed.backfill_closes(
        FakeConn(), "key", ["360750", "500001", "005930"], date(2024, 1, 1), date(2026, 1, 1)
    )

    url_of = dict(calls)
    assert url_of["360750"] == daily_price_seed._ETF_PRICE_URL
    assert url_of["500001"] == daily_price_seed._ETN_PRICE_URL
    assert url_of["005930"] == daily_price_seed._STOCK_PRICE_URL


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
