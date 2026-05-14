"""portfolio 라우터 테스트 — FakePool + quote mock."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch


from tests.conftest import TEST_USER_ID
from tests.fake_pool import FakeConnection, make_fake_acquire


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _make_trade_row(**kwargs) -> dict:
    now = _dt("2024-01-10T09:00:00+09:00")
    base = {
        "id": "t1",
        "user_id": TEST_USER_ID,
        "account_id": "a1",
        "asset_name": "삼성전자",
        "ticker_symbol": "005930",
        "market_type": "STOCK",
        "trade_type": "BUY",
        "price": 70000.0,
        "quantity": 10.0,
        "total_amount": 700000.0,
        "traded_at": now,
        "strategy_type": None,
        "reasoning_tags": [],
        "buy_reason": None,
        "sell_reason": None,
        "emotion": None,
        "result": None,
        "profit_loss": None,
        "avg_buy_price": None,
        "holding_days": None,
        "country_code": "KR",
        "exchange": "",
        "commission": 0.0,
        "tax": 0.0,
        "created_at": _dt("2024-01-01T00:00:00Z"),
        "updated_at": _dt("2024-01-01T00:00:00Z"),
        "account_name": None,
        "account_broker": None,
    }
    base.update(kwargs)
    return base


def _make_account_row(id_="a1") -> dict:
    return {
        "id": id_,
        "user_id": TEST_USER_ID,
        "name": "테스트 계좌",
        "broker": None,
        "cash_balance": 1000000.0,
        "created_at": _dt("2024-01-01T00:00:00Z"),
        "updated_at": _dt("2024-01-01T00:00:00Z"),
    }


def _to_record(d: dict):
    class R:
        def __init__(self, data):
            self._data = data
        def keys(self):
            return self._data.keys()
        def __getitem__(self, k):
            return self._data[k]
        def items(self):
            return self._data.items()
    return R(d)


def _patch_portfolio(conn: FakeConnection):
    return patch("invest_note_api.routers.portfolio.acquire_for_user", make_fake_acquire(conn))


class TestHolding:
    def test_holding_ok(self, trades_client):
        trade = _make_trade_row(trade_type="BUY", quantity=10)
        conn = FakeConnection([_to_record(trade)])
        with _patch_portfolio(conn):
            resp = trades_client.get(
                "/api/portfolio/holding",
                params={"accountId": "a1", "assetName": "삼성전자", "ticker": "005930", "country": "KR"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["quantity"] == 10.0

    def test_holding_missing_params_400(self, trades_client):
        resp = trades_client.get("/api/portfolio/holding")
        assert resp.status_code == 422  # FastAPI validation error for missing required params

    def test_no_holding_zero(self, trades_client):
        conn = FakeConnection([])
        with _patch_portfolio(conn):
            resp = trades_client.get(
                "/api/portfolio/holding",
                params={"accountId": "a1", "assetName": "삼성전자"},
            )
        assert resp.status_code == 200
        assert resp.json()["quantity"] == 0.0
        assert resp.json()["avgBuyPrice"] is None


class TestPortfolioSummary:
    def test_summary_ok_no_quotes(self, trades_client):
        trade = _make_trade_row()
        account = _make_account_row()

        conn = FakeConnection(
            [_to_record(trade)],    # trade_rows with account join
            [_to_record(account)],  # account_rows
        )

        async def mock_quotes(state, keys):
            return {}

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                resp = trades_client.get("/api/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        assert "totals" in body
        assert "positions" in body
        assert "snapshots" in body
        assert body["hasAccounts"] is True
        assert body["hasTrades"] is True

        # PnL 약어는 대문자 'L'로 직렬화 (FE 타입 호환). to_camel은 'Pnl'로
        # 변환되지만 to_camel_pnl wrapper가 'PnL'로 보정한다.
        pos = body["positions"][0]
        assert "realizedPnL" in pos
        assert "unrealizedPnL" in pos
        totals = body["totals"]
        assert "totalUnrealizedPnL" in totals
        assert "totalRealizedPnL" in totals
        assert "monthRealizedPnL" in totals

        # snapshot.account 중첩 객체는 snake_case 유지 (FE Account 타입 호환).
        snap_account = body["snapshots"][0]["account"]
        assert "user_id" in snap_account
        assert "cash_balance" in snap_account

    def test_summary_quote_failure_fallback(self, trades_client):
        """시세 fetch 실패 시에도 200 반환 (evaluation=null 허용)."""
        trade = _make_trade_row()
        account = _make_account_row()

        conn = FakeConnection(
            [_to_record(trade)],
            [_to_record(account)],
        )

        async def failing_quotes(state, keys):
            raise Exception("Naver down")

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", failing_quotes):
                resp = trades_client.get("/api/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        # evaluation이 없어도 정상 응답
        assert body["positions"][0]["currentPrice"] is None

    def test_summary_401(self, auth_client):
        resp = auth_client.get("/api/portfolio/summary")
        assert resp.status_code == 401
