"""trades 라우터 테스트 — FakePool 기반."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import asyncpg
import pytest

from invest_note_api.schemas.trade import TRADE_FREE_TEXT_MAX_LEN, TradeCreate
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
    holding_days=None,
    strategy_type=None,
    country_code="KR",
    exchange="",
    created_at=None,
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
        "strategy_type": strategy_type,
        "reasoning_tags": [],
        "buy_reason": None,
        "sell_reason": None,
        "emotion": None,
        "result": None,
        "profit_loss": profit_loss,
        "avg_buy_price": avg_buy_price,
        "holding_days": holding_days,
        "country_code": country_code,
        "exchange": exchange,
        "commission": 0.0,
        "tax": 0.0,
        "created_at": created_at or _dt("2024-01-01T00:00:00Z"),
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


def _capture_sql(monkeypatch) -> list[str]:
    """FakeConnection의 모든 DB 메서드를 spy해 실행 SQL을 기록."""
    calls: list[str] = []
    orig_execute = FakeConnection.execute
    orig_executemany = FakeConnection.executemany
    orig_fetch = FakeConnection.fetch
    orig_fetchval = FakeConnection.fetchval
    orig_fetchrow = FakeConnection.fetchrow

    async def spy_execute(self: Any, query: str, *args: Any) -> str:
        calls.append(query.strip())
        return await orig_execute(self, query, *args)

    async def spy_executemany(self: Any, query: str, args: Any) -> None:
        calls.append(query.strip())
        return await orig_executemany(self, query, args)

    async def spy_fetch(self: Any, query: str, *args: Any) -> list:
        calls.append(query.strip())
        return await orig_fetch(self, query, *args)

    async def spy_fetchval(self: Any, query: str, *args: Any) -> Any:
        calls.append(query.strip())
        return await orig_fetchval(self, query, *args)

    async def spy_fetchrow(self: Any, query: str, *args: Any) -> Any:
        calls.append(query.strip())
        return await orig_fetchrow(self, query, *args)

    monkeypatch.setattr(FakeConnection, "execute", spy_execute)
    monkeypatch.setattr(FakeConnection, "executemany", spy_executemany)
    monkeypatch.setattr(FakeConnection, "fetch", spy_fetch)
    monkeypatch.setattr(FakeConnection, "fetchval", spy_fetchval)
    monkeypatch.setattr(FakeConnection, "fetchrow", spy_fetchrow)
    return calls


def _assert_lock_before_list(sql_calls: list[str]) -> None:
    lock_idx = next(
        (i for i, q in enumerate(sql_calls) if "pg_advisory_xact_lock" in q.lower()), None
    )
    list_idx = next(
        (i for i, q in enumerate(sql_calls) if "from trades" in q.lower() and "where user_id" in q.lower()), None
    )
    assert lock_idx is not None, "pg_advisory_xact_lock 쿼리가 실행되지 않음"
    assert list_idx is not None, "list_trades 쿼리가 실행되지 않음"
    assert lock_idx < list_idx, f"lock(idx={lock_idx})이 list_trades(idx={list_idx})보다 늦게 실행됨"


def _assert_lock_timeout_before_lock(sql_calls: list[str]) -> None:
    timeout_idx = next(
        (i for i, q in enumerate(sql_calls) if "lock_timeout" in q.lower()), None
    )
    lock_idx = next(
        (i for i, q in enumerate(sql_calls) if "pg_advisory_xact_lock" in q.lower()), None
    )
    assert timeout_idx is not None, "SET LOCAL lock_timeout 쿼리가 실행되지 않음"
    assert lock_idx is not None, "pg_advisory_xact_lock 쿼리가 실행되지 않음"
    assert timeout_idx < lock_idx, f"lock_timeout(idx={timeout_idx})이 advisory lock(idx={lock_idx})보다 늦게 실행됨"


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

    def test_create_future_trade_400(self, trades_client):
        payload = {**self._buy_payload(), "traded_at": "2999-01-10T09:00:00"}
        resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 400
        assert "미래" in resp.json()["error"]

    def test_create_future_datetime_rejected_by_schema(self):
        payload = {
            **self._buy_payload(),
            "traded_at": datetime(2999, 1, 10, 0, 0, tzinfo=timezone.utc),
        }
        with pytest.raises(ValueError, match="미래"):
            TradeCreate.model_validate(payload)

    def test_create_foreign_buy_400_in_mvp(self, trades_client):
        payload = {
            **self._buy_payload(),
            "asset_name": "Apple",
            "ticker_symbol": "AAPL",
            "country_code": "US",
            "exchange": "NASDAQ",
        }
        resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 400
        assert "해외 주식 신규 매수" in resp.json()["error"]

    def test_create_foreign_sell_allowed_for_existing_holding(self, trades_client):
        acct_row = {"id": "a1"}
        buy_row = _make_trade_row(
            id_="b-us",
            trade_type="BUY",
            ticker="AAPL",
            asset_name="Apple",
            quantity=10,
            country_code="US",
            exchange="NASDAQ",
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        inserted = {"id": "new-us-sell", "trade_type": "SELL"}

        conn = FakeConnection(
            _to_record(acct_row),
            [_to_record(buy_row)],
            _to_record(inserted),
        )
        payload = {
            **self._buy_payload(),
            "trade_type": "SELL",
            "asset_name": "Apple",
            "ticker_symbol": "AAPL",
            "country_code": "US",
            "exchange": "NASDAQ",
        }
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-us-sell"

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

    def test_create_advisory_lock_before_list_trades(self, trades_client, monkeypatch):
        """BUY 생성 경로: pg_advisory_xact_lock이 list_trades보다 먼저 실행됨을 검증."""
        sql_calls = _capture_sql(monkeypatch)
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
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_create_sell_advisory_lock_before_list_trades(self, trades_client, monkeypatch):
        """SELL 생성 경로: pg_advisory_xact_lock이 list_trades보다 먼저 실행됨을 검증."""
        sql_calls = _capture_sql(monkeypatch)
        acct_row = {"id": "a1"}
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10,
                                  traded_at=_dt("2024-01-01T09:00:00+09:00"))
        inserted = {"id": "new-s1", "trade_type": "SELL"}
        conn = FakeConnection(
            _to_record(acct_row),      # account exists check
            [_to_record(buy_row)],     # list_trades
            _to_record(inserted),      # insert_trade RETURNING
        )
        payload = {**self._buy_payload(), "trade_type": "SELL"}
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=payload)
        assert resp.status_code == 201
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_create_lock_timeout_returns_409(self, trades_client, monkeypatch):
        """advisory lock 획득 실패(LockNotAvailableError) 시 409를 반환해야 함."""
        acct_row = {"id": "a1"}
        conn = FakeConnection(_to_record(acct_row))
        orig_fetchval = FakeConnection.fetchval

        async def spy_fetchval(self: Any, query: str, *args: Any) -> Any:
            if "pg_advisory_xact_lock" in query.lower():
                raise asyncpg.exceptions.LockNotAvailableError
            return await orig_fetchval(self, query, *args)

        monkeypatch.setattr(FakeConnection, "fetchval", spy_fetchval)
        with _patch_trades(conn):
            resp = trades_client.post("/api/trades", json=self._buy_payload())
        assert resp.status_code == 409
        assert "충돌" in resp.json()["error"]


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

    def test_patch_free_text_5000_chars_ok(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch(
                "/api/trades/t1",
                json={"buy_reason": "가" * TRADE_FREE_TEXT_MAX_LEN},
            )
        assert resp.status_code == 204

    def test_patch_free_text_5001_chars_400(self, trades_client):
        resp = trades_client.patch(
            "/api/trades/t1",
            json={"buy_reason": "가" * (TRADE_FREE_TEXT_MAX_LEN + 1)},
        )
        assert resp.status_code == 400
        assert "5000" in resp.json()["error"]

    def test_patch_not_found_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow returns None
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/nonexistent", json={"price": 75000})
        assert resp.status_code == 404

    def test_patch_pnl_advisory_lock_before_list_trades(self, trades_client, monkeypatch):
        """update_trade PnL 분기에서 lock이 list_trades보다 먼저 실행됨을 검증."""
        sql_calls = _capture_sql(monkeypatch)
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),   # existing fetchrow
            [_to_record(row)], # list_trades
            "UPDATE 1",        # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/t1", json={"price": 75000})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_patch_sell_emotion_only_ignored(self, trades_client, monkeypatch):
        """SELL의 emotion 단독 patch는 무시되어야 한다 — 자동 산출 정책."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))  # fetchrow만 호출, UPDATE 없음
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/s1", json={"emotion": "FOMO"})
        assert resp.status_code == 204
        # patch_trade의 SET 쿼리가 호출되지 않아야 함
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_sell_reasoning_tags_only_ignored(self, trades_client, monkeypatch):
        """SELL의 reasoning_tags 단독 patch도 무시."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/s1", json={"reasoning_tags": ["TECHNICAL"]})
        assert resp.status_code == 204
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_sell_emotion_with_pnl_field_strips_emotion(self, trades_client, monkeypatch):
        """SELL의 emotion과 price를 함께 patch하면 emotion만 빠지고 price는 처리되어야 한다."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            quantity=10,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        conn = FakeConnection(
            _to_record(sell_row),                          # fetchrow
            [_to_record(buy_row), _to_record(sell_row)],   # list_trades (PNL 분기)
            "UPDATE 1",                                    # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch(
                "/api/trades/s1",
                json={"emotion": "FOMO", "price": 90000},
            )
        assert resp.status_code == 204
        # patch_trade의 SET 쿼리가 emotion 없이 price만 포함해야 함
        patch_set = next(q for q in sql_calls if q.startswith("UPDATE trades SET") and "WHERE id" in q and "profit_loss" not in q)
        assert "price" in patch_set
        assert "emotion" not in patch_set

    def test_patch_buy_strategy_recalculates_matched_sell_strategy(self, trades_client, monkeypatch):
        """BUY 전략 수정은 이미 매칭된 SELL의 파생 strategy_type 재계산을 트리거해야 함."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(
            id_="b1",
            trade_type="BUY",
            quantity=10,
            strategy_type="SCALPING",
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            quantity=10,
            strategy_type="SCALPING",
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                         # existing fetchrow
            [_to_record(buy_row), _to_record(sell_row)], # list_trades
            "UPDATE 1",                                 # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/api/trades/b1", json={"strategy_type": "LONG_TERM"})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        assert any(
            "strategy_type = $4" in q and "UPDATE trades SET profit_loss" in q
            for q in sql_calls
        )


class TestDeleteTrade:
    def test_delete_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow → None → 404
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/nonexistent")
        assert resp.status_code == 404

    def test_delete_buy_ok(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),    # fetchrow target
            [_to_record(buy_row)],  # list_trades
            "DELETE 1",             # delete_trade
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/b1")
        assert resp.status_code == 204

    def test_delete_advisory_lock_before_list_trades(self, trades_client, monkeypatch):
        """delete_trade_endpoint에서 lock이 list_trades보다 먼저 실행됨을 검증."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),    # fetchrow target
            [_to_record(buy_row)],  # list_trades
            "DELETE 1",             # delete_trade
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/b1")
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_delete_oversell_validation_400(self, trades_client):
        """BUY 삭제 시 기존 SELL이 언더솔드되면 400을 반환해야 함."""
        buy_row = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1", trade_type="SELL", quantity=8,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                        # fetchrow target
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/api/trades/b1")
        assert resp.status_code == 400


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
                                  strategy_type="LONG_TERM",
                                  traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", price=80000, quantity=10,
                                   avg_buy_price=70000.0, profit_loss=100000.0,
                                   holding_days=31,
                                   strategy_type="LONG_TERM",
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
        assert body["strategyEvaluation"]["planned"] == "LONG_TERM"
        assert body["strategyEvaluation"]["actual"] == "LONG_TERM"
        assert body["strategyEvaluation"]["adherence"] == "FOLLOWED"

    def test_summary_holding_days_matches_strategy_evaluation_for_same_timestamp(self, trades_client):
        ts = _dt("2024-01-01T09:00:00+09:00")
        buy_row = _make_trade_row(
            id_="b1",
            trade_type="BUY",
            price=70000,
            quantity=10,
            strategy_type="SCALPING",
            traded_at=ts,
            created_at=_dt("2024-01-01T00:00:00Z"),
        )
        sell_row = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            price=70000,
            quantity=10,
            avg_buy_price=70000.0,
            profit_loss=0.0,
            holding_days=0,
            strategy_type="SCALPING",
            traded_at=ts,
            created_at=_dt("2024-01-01T00:00:01Z"),
        )

        conn = FakeConnection(
            _to_record(sell_row),
            [_to_record(sell_row), _to_record(buy_row)],
        )
        with _patch_trades(conn):
            resp = trades_client.get("/api/trades/s1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["holdingDays"] == 0
        assert body["strategyEvaluation"]["holdingDays"] == 0

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
