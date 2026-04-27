"""stocks 라우터 테스트 — quote + search."""
from __future__ import annotations

from unittest.mock import patch


class TestStocksQuote:
    def test_quote_ok(self, trades_client):
        async def mock_quotes(keys):
            return {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": "2024-01-15"}}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/api/stocks/quote", params={"symbols": "005930:KR"})

        assert resp.status_code == 200
        body = resp.json()
        assert "005930:KR" in body
        assert body["005930:KR"]["price"] == 75000.0

    def test_quote_empty_returns_empty(self, trades_client):
        async def mock_quotes(keys):
            return {}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/api/stocks/quote", params={"symbols": ""})

        assert resp.status_code == 200
        assert resp.json() == {}

    def test_quote_us_returns_null_in_mvp(self, trades_client):
        async def mock_quotes(keys):
            return {"AAPL:US": None}

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/api/stocks/quote", params={"symbols": "AAPL:US"})

        assert resp.status_code == 200
        assert resp.json()["AAPL:US"] is None

    def test_quote_mixed(self, trades_client):
        async def mock_quotes(keys):
            return {
                "005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": ""},
                "AAPL:US": None,
            }

        with patch("invest_note_api.routers.stocks.fetch_quotes_by_keys", mock_quotes):
            resp = trades_client.get("/api/stocks/quote", params={"symbols": "005930:KR,AAPL:US"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["005930:KR"]["price"] == 75000.0
        assert body["AAPL:US"] is None

    def test_quote_401(self, auth_client):
        resp = auth_client.get("/api/stocks/quote", params={"symbols": "005930:KR"})
        assert resp.status_code == 401


class TestStocksSearch:
    def test_search_kr_by_korean(self, trades_client):
        async def mock_search_kr(q):
            return [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}]

        with patch("invest_note_api.routers.stocks._search_kr", mock_search_kr):
            resp = trades_client.get("/api/stocks/search", params={"q": "삼성"})

        assert resp.status_code == 200
        assert resp.json()[0]["code"] == "005930"
        assert resp.json()[0]["market"] == "KR"

    def test_search_kr_by_6digit_code(self, trades_client):
        async def mock_search_kr(q):
            return [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": ""}]

        with patch("invest_note_api.routers.stocks._search_kr", mock_search_kr):
            resp = trades_client.get("/api/stocks/search", params={"q": "005930"})

        assert resp.status_code == 200
        assert resp.json()[0]["market"] == "KR"

    def test_search_english_returns_empty_in_mvp(self, trades_client):
        async def mock_search_kr(q):
            return []

        with patch("invest_note_api.routers.stocks._search_kr", mock_search_kr):
            resp = trades_client.get("/api/stocks/search", params={"q": "apple"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_empty_query_empty_result(self, trades_client):
        resp = trades_client.get("/api/stocks/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_401(self, auth_client):
        resp = auth_client.get("/api/stocks/search", params={"q": "삼성"})
        assert resp.status_code == 401
