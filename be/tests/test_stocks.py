"""stocks 라우터 테스트 — quote + search."""
from __future__ import annotations

from unittest.mock import patch

from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from tests.fake_pool import FakeConnection, make_fake_pool


def _use_fake_pool(client, conn: FakeConnection | None = None) -> None:
    """search 엔드포인트의 pool.acquire() 가 동작하도록 get_pool 을 fake pool 로 override."""
    client.app.dependency_overrides[get_pool] = lambda: make_fake_pool(conn)


def _use_db_provider(client) -> None:
    """search 엔드포인트를 로컬 DB 경로로 고정 (기본값은 naver 이므로 명시 override)."""
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://test.supabase.co", stock_search_provider="db"
    )


class TestStocksQuote:
    def test_quote_ok(self, trades_client):
        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None):
            return {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": "2024-01-15"}}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/stocks/quote", params={"symbols": "005930:KR"})

        assert resp.status_code == 200
        body = resp.json()
        assert "005930:KR" in body
        assert body["005930:KR"]["price"] == 75000.0

    def test_quote_empty_returns_empty(self, trades_client):
        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None):
            return {}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/stocks/quote", params={"symbols": ""})

        assert resp.status_code == 200
        assert resp.json() == {}

    def test_quote_us_returns_null_in_mvp(self, trades_client):
        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None):
            return {"AAPL:US": None}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/stocks/quote", params={"symbols": "AAPL:US"})

        assert resp.status_code == 200
        assert resp.json()["AAPL:US"] is None

    def test_quote_forwards_env_providers(self, trades_client):
        """QUOTE_PROVIDERS env(settings) 가 fetch_quotes_by_keys 의 providers 로 전달된다 —
        env 토글이 죽은 설정이 되지 않음을 보장하는 통합 가드."""
        received: dict = {}

        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None):
            received["providers"] = providers
            return {}

        trades_client.app.dependency_overrides[get_settings] = lambda: Settings(
            supabase_url="https://test.supabase.co", quote_providers="yahoo"
        )
        try:
            with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
                resp = trades_client.get("/stocks/quote", params={"symbols": "005930:KR"})
        finally:
            trades_client.app.dependency_overrides.pop(get_settings, None)

        assert resp.status_code == 200
        assert received["providers"] == ["yahoo"]

    def test_quote_mixed(self, trades_client):
        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None):
            return {
                "005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": ""},
                "AAPL:US": None,
            }

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/stocks/quote", params={"symbols": "005930:KR,AAPL:US"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["005930:KR"]["price"] == 75000.0
        assert body["AAPL:US"] is None

    def test_quote_401(self, auth_client):
        resp = auth_client.get("/stocks/quote", params={"symbols": "005930:KR"})
        assert resp.status_code == 401


class TestStocksMeta:
    def test_meta_ok(self, trades_client):
        async def mock_meta(conn, codes, **kw):
            return {
                "005930": {"market": "KOSPI", "marcap_rank": 1,
                           "nps_holding": "major", "nps_as_of": "2026-03-31"},
            }

        _use_fake_pool(trades_client)
        with patch("invest_note_api.db_ops.stocks_repo.fetch_meta", mock_meta):
            resp = trades_client.get("/stocks/meta", params={"codes": "005930"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["005930"]["market"] == "KOSPI"
        assert body["005930"]["marcap_rank"] == 1
        assert body["005930"]["nps_holding"] == "major"

    def test_meta_empty_returns_empty(self, trades_client):
        _use_fake_pool(trades_client)
        resp = trades_client.get("/stocks/meta", params={"codes": ""})
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_meta_401(self, auth_client):
        resp = auth_client.get("/stocks/meta", params={"codes": "005930"})
        assert resp.status_code == 401


class TestStocksSearchDb:
    """provider=db — 로컬 stocks 마스터 조회 경로."""

    def test_search_by_korean(self, trades_client):
        async def mock_search(conn, q, **kw):
            return [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}]

        _use_db_provider(trades_client)
        _use_fake_pool(trades_client)
        with patch("invest_note_api.db_ops.stocks_repo.search", mock_search):
            resp = trades_client.get("/stocks/search", params={"q": "삼성"})

        assert resp.status_code == 200
        assert resp.json()[0]["code"] == "005930"
        assert resp.json()[0]["market"] == "KR"

    def test_search_by_6digit_code(self, trades_client):
        async def mock_search(conn, q, **kw):
            return [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}]

        _use_db_provider(trades_client)
        _use_fake_pool(trades_client)
        with patch("invest_note_api.db_ops.stocks_repo.search", mock_search):
            resp = trades_client.get("/stocks/search", params={"q": "005930"})

        assert resp.status_code == 200
        assert resp.json()[0]["market"] == "KR"

    def test_search_no_match_returns_empty(self, trades_client):
        async def mock_search(conn, q, **kw):
            return []

        _use_db_provider(trades_client)
        _use_fake_pool(trades_client)
        with patch("invest_note_api.db_ops.stocks_repo.search", mock_search):
            resp = trades_client.get("/stocks/search", params={"q": "apple"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestStocksSearchNaver:
    """provider=naver (기본값) — Naver 자동완성 라이브 호출 경로."""

    def test_default_provider_uses_naver(self, trades_client):
        captured: dict = {}

        async def mock_naver(q, *, client=None):
            captured["q"] = q
            return [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}]

        # 기본값(provider 미설정)이 naver 임을 검증 — get_settings override 없음.
        with patch("invest_note_api.routers.stocks.search_kr", mock_naver):
            resp = trades_client.get("/stocks/search", params={"q": "삼성"})

        assert resp.status_code == 200
        assert captured["q"] == "삼성"
        assert resp.json()[0]["code"] == "005930"

    def test_naver_no_match_returns_empty(self, trades_client):
        async def mock_naver(q, *, client=None):
            return []

        with patch("invest_note_api.routers.stocks.search_kr", mock_naver):
            resp = trades_client.get("/stocks/search", params={"q": "apple"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestStocksSearch:
    def test_search_empty_query_empty_result(self, trades_client):
        resp = trades_client.get("/stocks/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_401(self, auth_client):
        resp = auth_client.get("/stocks/search", params={"q": "삼성"})
        assert resp.status_code == 401
