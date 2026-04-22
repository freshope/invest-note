"""trades 라우터 테스트 — FakePool 기반."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch


from tests.conftest import TEST_USER_ID
from tests.fake_pool import FakeConnection, make_fake_acquire


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _make_trade_row(
    id_="t1",
    trade_type="BUY",
    account_id="a1",
    ticker="005930",
    asset_name="삼성전자",
    price=70000.0,
    quantity=10.0,
    traded_at=None,
    profit_loss=None,
    avg_buy_price=None,
) -> dict:
    now = _dt("2024-01-10T09:00:00+09:00")
    return {
        "id": id_,
        "user_id": TEST_USER_ID,
        "account_id": account_id,
        "asset_name": asset_name,
        "ticker_symbol": ticker,
        "market_type": "STOCK",
        "trade_type": trade_type,
        "price": price,
        "quantity": quantity,
        "total_amount": price * quantity,
        "traded_at": traded_at or now,
        "strategy_type": None,
        "reasoning_tags": [],
        "buy_reason": None,
        "sell_reason": None,
        "emotion": None,
        "result": None,
        "reflection_note": None,
        "improvement_note": None,
        "profit_loss": profit_loss,
        "avg_buy_price": avg_buy_price,
        "country_code": "KR",
        "exchange": "",
        "commission": 0.0,
        "tax": 0.0,
        "created_at": _dt("2024-01-01T00:00:00Z"),
        "updated_at": _dt("2024-01-01T00:00:00Z"),
        "account_name": None,
        "account_broker": None,
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


def _patch_trades(conn: FakeConnection):
    return patch("invest_note_api.routers.trades.acquire_for_user", make_fake_acquire(conn))


class TestListTrades:
    def test_list_returns_200(self, trades_client):
        trade_row = _make_trade_row()
        conn = FakeConnection(
            [_to_record(trade_row)],   # list_trades_with_account
            [],                         # accounts
        )
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert "trades" in body
        assert "accounts" in body

    def test_list_ticker_filter(self, trades_client):
        trade_row = _make_trade_row()
        conn = FakeConnection(
            [_to_record(trade_row)],
            [],
        )
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades", params={"ticker": "005930", "country": "KR"})
        assert resp.status_code == 200

    def test_list_invalid_ticker_400(self, trades_client):
        resp = trades_client.get("/api/trades", params={"ticker": "/../etc/passwd"})
        assert resp.status_code == 400


class TestCreateTrade:
    def _buy_payload(self, account_id="a1") -> dict:
        return {
            "trade_type": "BUY",
            "market_type": "STOCK",
            "account_id": account_id,
            "asset_name": "삼성전자",
            "ticker_symbol": "005930",
            "country_code": "KR",
            "exchange": "KOSPI",
            "traded_at": "2024-01-10T09:00:00",
            "price": 70000,
            "quantity": 10,
            "commission": 0,
            "tax": 0,
        }

    def test_create_buy_201(self, trades_client):
        acct_row = {"id": "a1"}
        trade_row = _make_trade_row()
        inserted = {"id": "new-t1", "trade_type": "BUY"}

        conn = FakeConnection(
            _to_record(acct_row),      # account exists check
            [_to_record(trade_row)],   # list_trades
            _to_record(inserted),      # insert_trade RETURNING
        )
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=self._buy_payload())
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-t1"

    def test_invalid_body_400(self, trades_client):
        resp = trades_client.post("/api/trades", json={"trade_type": "BUY"})
        assert resp.status_code == 400

    def test_sell_no_holding_400(self, trades_client):
        acct_row = {"id": "a1"}
        conn = FakeConnection(
            _to_record(acct_row),  # account exists
            [],                     # list_trades → empty
        )
        payload = {**self._buy_payload(), "trade_type": "SELL"}
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 400
        assert "보유" in resp.json()["error"]

    def test_create_sell_ok(self, trades_client):
        acct_row = {"id": "a1"}
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10,
                                  traded_at=_dt("2024-01-01T09:00:00+09:00"))
        inserted = {"id": "new-s1", "trade_type": "SELL"}

        conn = FakeConnection(
            _to_record(acct_row),
            [_to_record(buy_row)],
            _to_record(inserted),
        )
        payload = {**self._buy_payload(), "trade_type": "SELL"}
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 201


class TestGetTrade:
    def test_get_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/nonexistent")
        assert resp.status_code == 404

    def test_get_200(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(_to_record(row))
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/t1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "t1"


class TestPatchTrade:
    def test_empty_body_204(self, trades_client):
        # No acquire call needed — returns 204 before DB
        resp = trades_client.patch("/api/trades/t1", json={})
        assert resp.status_code == 204

    def test_patch_non_pnl_field(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/t1", json={"buy_reason": "테스트"})
        assert resp.status_code == 204

    def test_patch_not_found_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow returns None
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/nonexistent", json={"price": 75000})
        assert resp.status_code == 404


class TestDeleteTrade:
    def test_delete_404(self, trades_client):
        conn = FakeConnection([])  # empty list → target not found
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/nonexistent")
        assert resp.status_code == 404

    def test_delete_buy_ok(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            [_to_record(buy_row)],  # list_trades
            "DELETE 1",             # delete_trade
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/b1")
        assert resp.status_code == 204


class TestTradeSummary:
    def test_summary_non_sell_400(self, trades_client):
        row = _make_trade_row(id_="b1", trade_type="BUY")
        conn = FakeConnection(
            _to_record(row),  # sell_row query → BUY trade
            [],               # list_trades (unreached)
        )
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/b1/summary")
        assert resp.status_code == 400

    def test_summary_sell_200(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", price=70000, quantity=10,
                                  traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", price=80000, quantity=10,
                                   avg_buy_price=70000.0, profit_loss=100000.0,
                                   traded_at=_dt("2024-02-01T09:00:00+09:00"))

        conn = FakeConnection(
            _to_record(sell_row),
            [_to_record(buy_row), _to_record(sell_row)],
        )
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/s1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "pnl" in body
        assert "breakdown" in body
        assert body["pnl"] == 100000.0

    def test_summary_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/nonexistent/summary")
        assert resp.status_code == 404


class TestTradesAuth:
    def test_no_token_401(self, auth_client):
        resp = auth_client.get("/api/trades")
        assert resp.status_code == 401

    def test_invalid_token_401(self, auth_client):
        resp = auth_client.get("/api/trades", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
