"""trades 라우터 테스트 — FakePool 기반."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import uuid4

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
    result=None,
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
        "result": result,
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
            resp = trades_client.get("/trades")
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
            resp = trades_client.get("/trades", params={"ticker": "005930", "country": "KR"})
        assert resp.status_code == 200

    def test_list_ticker_pushed_to_sql(self, trades_client, monkeypatch):
        """ticker/country 가 SQL fetch 인자로 전달되는지 검증 (Python 후처리 X)."""
        captured: list[tuple[str, tuple[Any, ...]]] = []
        orig_fetch = FakeConnection.fetch

        async def spy_fetch(self: Any, query: str, *args: Any) -> list:
            captured.append((query, args))
            return await orig_fetch(self, query, *args)

        monkeypatch.setattr(FakeConnection, "fetch", spy_fetch)

        conn = FakeConnection([_to_record(_make_trade_row())], [])
        with _patch_trades(conn):
            resp = trades_client.get("/trades", params={"ticker": "005930", "country": "KR"})
        assert resp.status_code == 200

        list_calls = [
            (q, a) for q, a in captured
            if "from trades t" in q.lower() and "left join accounts" in q.lower()
        ]
        assert len(list_calls) == 1, f"trades+accounts list 쿼리가 1회 실행되어야 함: {list_calls}"
        q, args = list_calls[0]
        assert "t.ticker_symbol = $2" in q
        assert "country_code" in q and "$3" in q
        assert str(args[0]) == str(TEST_USER_ID)
        assert args[1:] == ("005930", "KR")

    def test_list_invalid_ticker_400(self, trades_client):
        resp = trades_client.get("/trades", params={"ticker": "/../etc/passwd"})
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
            resp = trades_client.post("/trades", json=self._buy_payload())
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-t1"

    def test_invalid_body_422(self, trades_client):
        resp = trades_client.post("/trades", json={"trade_type": "BUY"})
        assert resp.status_code == 422

    def test_create_future_trade_422(self, trades_client):
        payload = {**self._buy_payload(), "traded_at": "2999-01-10T09:00:00"}
        resp = trades_client.post("/trades", json=payload)
        assert resp.status_code == 422
        assert "미래" in resp.json()["error"]

    def test_create_future_datetime_rejected_by_schema(self):
        payload = {
            **self._buy_payload(),
            "traded_at": datetime(2999, 1, 10, 0, 0, tzinfo=timezone.utc),
        }
        with pytest.raises(ValueError, match="미래"):
            TradeCreate.model_validate(payload)

    def test_create_foreign_buy_422_in_mvp(self, trades_client):
        payload = {
            **self._buy_payload(),
            "asset_name": "Apple",
            "ticker_symbol": "AAPL",
            "country_code": "US",
            "exchange": "NASDAQ",
        }
        resp = trades_client.post("/trades", json=payload)
        assert resp.status_code == 422
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
            resp = trades_client.post("/trades", json=payload)
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
            resp = trades_client.post("/trades", json=payload)
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
            resp = trades_client.post("/trades", json=payload)
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
            resp = trades_client.post("/trades", json=self._buy_payload())
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
            resp = trades_client.post("/trades", json=payload)
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
            resp = trades_client.post("/trades", json=self._buy_payload())
        assert resp.status_code == 409
        assert "충돌" in resp.json()["error"]


class TestImportCommit:
    def _staged_row(
        self,
        ticker: str,
        asset_name: str,
        traded_at_kst: str = "2024-01-10",
    ) -> dict:
        return {
            "asset_name": asset_name,
            "ticker_symbol": ticker,
            "market_type": "STOCK",
            "trade_type": "BUY",
            "price": 70000,
            "quantity": 1,
            "traded_at_kst": traded_at_kst,
            "commission": 0,
            "tax": 0,
            "country_code": "KR",
            "exchange": "KOSPI",
        }

    def test_commit_fetches_per_group(
        self,
        trades_client,
        monkeypatch,
    ):
        sql_calls = _capture_sql(monkeypatch)
        staging_id = str(uuid4())

        trades_client.app.state.trade_staging.cache[staging_id] = {
            "user_id": TEST_USER_ID,
            "rows": [
                self._staged_row("005930", "삼성전자"),
                self._staged_row("000660", "SK하이닉스"),
            ],
            "parse_errors": [],
            "usd_skip_count": 0,
            "broker_key": "toss",
            "account_hint": None,
        }

        conn = FakeConnection(
            "a1",  # assert_account_exists
            [],  # group 1 list_trades_in_group (삼성전자)
            [_to_record(_make_trade_row(id_="new-1", ticker="005930", asset_name="삼성전자"))],
            [],  # group 2 list_trades_in_group (SK하이닉스)
            [_to_record(_make_trade_row(id_="new-2", ticker="000660", asset_name="SK하이닉스"))],
        )

        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )

        assert resp.status_code == 200
        assert resp.json()["inserted_count"] == 2
        list_trade_calls = [
            q for q in sql_calls
            if q.lower().startswith("select * from trades")
            and "where user_id = $1" in q.lower()
        ]
        # 그룹 단위 fetch — 그룹 수만큼 호출
        assert len(list_trade_calls) == 2

    # ── 머지 케이스 ─────────────────────────────────────────────────────────

    def _merge_row(
        self,
        *,
        ticker: str = "005930",
        asset_name: str = "삼성전자",
        traded_at_kst: str = "2024-01-10",
        trade_type: str = "BUY",
        price: float = 70000,
        quantity: float = 1,
        commission: float = 0,
        tax: float = 0,
        traded_at_kst_full: str | None = None,
    ) -> dict:
        return {
            "asset_name": asset_name,
            "ticker_symbol": ticker,
            "market_type": "STOCK",
            "trade_type": trade_type,
            "price": price,
            "quantity": quantity,
            "traded_at_kst": traded_at_kst,
            "traded_at_kst_full": traded_at_kst_full,
            "commission": commission,
            "tax": tax,
            "country_code": "KR",
            "exchange": "",
        }

    def _stage(self, trades_client, rows: list[dict]) -> str:
        staging_id = str(uuid4())
        trades_client.app.state.trade_staging.cache[staging_id] = {
            "user_id": TEST_USER_ID,
            "rows": rows,
            "parse_errors": [],
            "usd_skip_count": 0,
            "broker_key": "samsung_xlsx",
            "account_hint": None,
        }
        return staging_id

    def test_merge_updates_commission_tax(self, trades_client, monkeypatch):
        """동일 시그니처 + commission/tax 변경 → 머지 1건, INSERT 0건."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(commission=100.0, tax=50.0)],
        )
        existing = _to_record(_make_trade_row(
            id_="existing-1", ticker="005930", asset_name="삼성전자",
            price=70000, quantity=1,
            traded_at=_dt("2024-01-10T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing])

        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 0
        assert body["merged_count"] == 1
        assert body["skipped_count"] == 0

        merge_updates = [
            q for q in sql_calls
            if q.lower().startswith("update trades set")
            and "commission" in q.lower()
            and "profit_loss" not in q.lower()  # recalc UPDATE 와 구분
        ]
        assert len(merge_updates) == 1
        assert "tax" in merge_updates[0].lower()

    def test_merge_preserves_user_meta_in_update_sql(self, trades_client, monkeypatch):
        """머지 UPDATE 에 사용자 메타 필드가 포함되지 않는다."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(commission=200.0)],
        )
        existing = _to_record(_make_trade_row(
            id_="existing-1", ticker="005930", asset_name="삼성전자",
            price=70000, quantity=1,
            traded_at=_dt("2024-01-10T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing])

        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        merge_updates = [
            q for q in sql_calls
            if q.lower().startswith("update trades set")
            and "commission" in q.lower()
            and "profit_loss" not in q.lower()
        ]
        assert len(merge_updates) == 1
        update_sql = merge_updates[0].lower()
        for forbidden in (
            "strategy_type", "buy_reason", "sell_reason", "emotion", "reasoning_tags",
            "price", "quantity", "asset_name", "ticker_symbol", "trade_type",
        ):
            assert forbidden not in update_sql, f"머지 UPDATE 에 {forbidden} 포함됨: {update_sql}"

    def test_merge_traded_at_when_kst_full_present(self, trades_client, monkeypatch):
        """traded_at_kst_full 시각 정보가 다르면 traded_at 도 머지 UPDATE 에 포함."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(
                commission=100.0,
                traded_at_kst_full="2024-01-10 14:30:00",
            )],
        )
        # 기존은 09:00, 머지로 14:30 으로 갱신되어야 함
        existing = _to_record(_make_trade_row(
            id_="existing-1", ticker="005930", asset_name="삼성전자",
            price=70000, quantity=1,
            traded_at=_dt("2024-01-10T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing])

        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        assert resp.json()["merged_count"] == 1

        merge_updates = [
            q for q in sql_calls
            if q.lower().startswith("update trades set")
            and "commission" in q.lower()
            and "profit_loss" not in q.lower()
        ]
        assert len(merge_updates) == 1
        assert "traded_at" in merge_updates[0].lower()

    def test_skipped_when_completely_identical(self, trades_client, monkeypatch):
        """commission/tax 까지 완전히 동일 → merged_count 0, skipped_count 1."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(commission=0.0, tax=0.0)],
        )
        existing = _to_record(_make_trade_row(
            id_="existing-1", ticker="005930", asset_name="삼성전자",
            price=70000, quantity=1,
            traded_at=_dt("2024-01-10T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing])

        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 0
        assert body["merged_count"] == 0
        assert body["skipped_count"] == 1

        # 머지 UPDATE 호출 없어야 함
        merge_updates = [
            q for q in sql_calls
            if q.lower().startswith("update trades set")
            and "commission" in q.lower()
            and "profit_loss" not in q.lower()
        ]
        assert merge_updates == []

    def test_buy_sell_same_qty_price_inserted_separately(self, trades_client, monkeypatch):
        """같은 date/ticker/price/quantity 의 BUY 와 SELL → 둘 다 별도 INSERT, 머지/skip 아님."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [
                self._merge_row(trade_type="BUY"),
                self._merge_row(trade_type="SELL"),
            ],
        )
        # 그룹에 기존 거래 없음 → 둘 다 신규 INSERT
        conn = FakeConnection(
            "a1",
            [],  # list_trades_in_group: 빈 리스트
            [   # insert_trades_bulk: 2건 RETURNING
                _to_record(_make_trade_row(id_="new-buy", trade_type="BUY",
                                           traded_at=_dt("2024-01-10T09:00:00+09:00"))),
                _to_record(_make_trade_row(id_="new-sell", trade_type="SELL",
                                           traded_at=_dt("2024-01-10T09:00:00+09:00"))),
            ],
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 2
        assert body["merged_count"] == 0
        assert body["skipped_count"] == 0

        # INSERT INTO trades 가 한 번 호출되어 2건 RETURNING
        inserts = [q for q in sql_calls if q.lower().startswith("insert into trades")]
        assert len(inserts) == 1

    # ── 정합성 (oversell) 검증 ────────────────────────────────────────────

    def test_sell_without_existing_buy_rejected_before_db_change(
        self, trades_client, monkeypatch
    ):
        """기존 BUY 없는 종목에 SELL 만 import → DB 변경 없이 error 1.

        INSERT/UPDATE 가 호출되지 않아야 한다 (검증을 DB 적용 전에 수행).
        """
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(trade_type="SELL")],
        )
        conn = FakeConnection(
            "a1",
            [],  # list_trades_in_group: 기존 거래 없음
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 0
        assert body["merged_count"] == 0
        assert body["error_count"] == 1
        assert "보유 수량이 없습니다" in body["errors"][0]["reason"]

        # INSERT / UPDATE 가 한 번도 호출되지 않아야 함
        inserts = [q for q in sql_calls if q.lower().startswith("insert into trades")]
        updates = [q for q in sql_calls if q.lower().startswith("update trades set")]
        assert inserts == []
        assert updates == []

    def test_sell_exceeding_holding_rejected_before_db_change(
        self, trades_client, monkeypatch
    ):
        """보유 수량보다 큰 SELL import → DB 변경 없이 error 1."""
        sql_calls = _capture_sql(monkeypatch)
        staging_id = self._stage(
            trades_client,
            [self._merge_row(trade_type="SELL", quantity=2)],
        )
        existing_buy = _to_record(_make_trade_row(
            id_="existing-buy", trade_type="BUY", quantity=1, price=70000,
            traded_at=_dt("2024-01-09T09:00:00+09:00"),
        ))
        conn = FakeConnection(
            "a1",
            [existing_buy],  # list_trades_in_group: BUY 1주 보유
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 0
        assert body["error_count"] == 1
        assert "초과" in body["errors"][0]["reason"]

        inserts = [q for q in sql_calls if q.lower().startswith("insert into trades")]
        updates = [q for q in sql_calls if q.lower().startswith("update trades set")]
        assert inserts == []
        assert updates == []

    def test_oversell_in_one_group_does_not_block_other_groups(
        self, trades_client, monkeypatch
    ):
        """한 종목이 oversell 이어도 다른 정상 종목은 INSERT 되어야 한다."""
        staging_id = self._stage(
            trades_client,
            [
                # 그룹 1: 정상 BUY
                self._merge_row(ticker="005930", asset_name="삼성전자", trade_type="BUY"),
                # 그룹 2: 보유 없이 SELL → oversell (DB 변경 없음)
                self._merge_row(ticker="000660", asset_name="SK하이닉스", trade_type="SELL"),
            ],
        )
        conn = FakeConnection(
            "a1",
            [],  # 그룹 1 list_trades_in_group
            [   # 그룹 1 insert_trades_bulk RETURNING
                _to_record(_make_trade_row(
                    id_="new-1", ticker="005930", asset_name="삼성전자",
                    trade_type="BUY",
                    traded_at=_dt("2024-01-10T09:00:00+09:00"),
                )),
            ],
            [],  # 그룹 2 list_trades_in_group (검증에서 reject → INSERT 호출 안 됨)
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 1  # 삼성전자 BUY 만
        assert body["error_count"] == 1
        assert "SK하이닉스" in body["errors"][0]["reason"]


class TestImportPreviewValidation:
    """import_preview 의 _validate_import_groups 흐름 단위 테스트."""

    def _row(
        self,
        *,
        ticker: str = "005930",
        asset_name: str = "삼성전자",
        traded_at_kst: str = "2024-01-10",
        trade_type: str = "BUY",
        price: float = 70000,
        quantity: float = 1,
    ) -> dict:
        return {
            "asset_name": asset_name,
            "ticker_symbol": ticker,
            "market_type": "STOCK",
            "trade_type": trade_type,
            "price": price,
            "quantity": quantity,
            "traded_at_kst": traded_at_kst,
            "traded_at_kst_full": None,
            "commission": 0,
            "tax": 0,
            "country_code": "KR",
            "exchange": "",
        }

    @pytest.mark.asyncio
    async def test_sell_only_returns_validation_error(self):
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [self._row(trade_type="SELL")]
        conn = FakeConnection(
            "a1",  # assert_account_exists
            [],    # list_trades_in_group (빈 그룹)
        )
        with patch(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(conn),
        ):
            errors, excluded_count = await _validate_import_groups(
                pool=None, user_id=TEST_USER_ID, account_id="a1", rows=rows,
            )
        assert len(errors) == 1
        assert "보유 수량이 없습니다" in errors[0].reason
        assert "나머지 거래만 등록됩니다" in errors[0].reason
        assert excluded_count == 1

    @pytest.mark.asyncio
    async def test_buy_and_sell_in_same_batch_pass(self):
        """같은 batch 안 BUY → SELL 정렬 후 매칭되면 검증 통과."""
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [
            self._row(trade_type="BUY", quantity=1),
            self._row(trade_type="SELL", quantity=1),
        ]
        conn = FakeConnection("a1", [])
        with patch(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(conn),
        ):
            errors, excluded_count = await _validate_import_groups(
                pool=None, user_id=TEST_USER_ID, account_id="a1", rows=rows,
            )
        assert errors == []
        assert excluded_count == 0

    @pytest.mark.asyncio
    async def test_sell_exceeding_existing_returns_validation_error(self):
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [self._row(trade_type="SELL", quantity=2)]
        existing_buy = _to_record(_make_trade_row(
            id_="existing-buy", trade_type="BUY", quantity=1, price=70000,
            traded_at=_dt("2024-01-09T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing_buy])
        with patch(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(conn),
        ):
            errors, excluded_count = await _validate_import_groups(
                pool=None, user_id=TEST_USER_ID, account_id="a1", rows=rows,
            )
        assert len(errors) == 1
        assert "초과" in errors[0].reason
        assert excluded_count == 1

    @pytest.mark.asyncio
    async def test_excluded_count_sums_rows_in_invalid_groups(self):
        """문제 그룹(SELL 보유부족)의 import row 수가 excluded_count 에 합산된다."""
        from invest_note_api.routers.trades import _validate_import_groups

        # 같은 종목 그룹: BUY 1건 + SELL 2건 → 총 3건 모두 제외 대상
        rows = [
            self._row(trade_type="BUY", quantity=1),
            self._row(trade_type="SELL", quantity=2, traded_at_kst="2024-01-11"),
            self._row(trade_type="SELL", quantity=3, traded_at_kst="2024-01-12"),
        ]
        conn = FakeConnection("a1", [])
        with patch(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(conn),
        ):
            errors, excluded_count = await _validate_import_groups(
                pool=None, user_id=TEST_USER_ID, account_id="a1", rows=rows,
            )
        assert len(errors) == 1
        assert excluded_count == 3


class TestGetTrade:
    def test_get_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/trades/nonexistent")
        assert resp.status_code == 404

    def test_get_200(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(_to_record(row))
        with _patch_trades(conn):
            resp = trades_client.get("/trades/t1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "t1"


class TestPatchTrade:
    def test_empty_body_204(self, trades_client):
        # No acquire call needed — returns 204 before DB
        resp = trades_client.patch("/trades/t1", json={})
        assert resp.status_code == 204

    def test_patch_non_pnl_field(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/trades/t1", json={"buy_reason": "테스트"})
        assert resp.status_code == 204

    def test_patch_free_text_5000_chars_ok(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch(
                "/trades/t1",
                json={"buy_reason": "가" * TRADE_FREE_TEXT_MAX_LEN},
            )
        assert resp.status_code == 204

    def test_patch_free_text_5001_chars_422(self, trades_client):
        resp = trades_client.patch(
            "/trades/t1",
            json={"buy_reason": "가" * (TRADE_FREE_TEXT_MAX_LEN + 1)},
        )
        assert resp.status_code == 422
        assert "5000" in resp.json()["error"]

    def test_patch_not_found_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow returns None
        with _patch_trades(conn):
            resp = trades_client.patch("/trades/nonexistent", json={"price": 75000})
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
            resp = trades_client.patch("/trades/t1", json={"price": 75000})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_patch_sell_emotion_only_ignored(self, trades_client, monkeypatch):
        """SELL의 emotion 단독 patch는 무시되어야 한다 — 자동 산출 정책."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))  # fetchrow만 호출, UPDATE 없음
        with _patch_trades(conn):
            resp = trades_client.patch("/trades/s1", json={"emotion": "FOMO"})
        assert resp.status_code == 204
        # patch_trade의 SET 쿼리가 호출되지 않아야 함
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_sell_reasoning_tags_only_ignored(self, trades_client, monkeypatch):
        """SELL의 reasoning_tags 단독 patch도 무시."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))
        with _patch_trades(conn):
            resp = trades_client.patch("/trades/s1", json={"reasoning_tags": ["TECHNICAL"]})
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
                "/trades/s1",
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
            resp = trades_client.patch("/trades/b1", json={"strategy_type": "LONG_TERM"})
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
            resp = trades_client.delete("/trades/nonexistent")
        assert resp.status_code == 404

    def test_delete_buy_ok(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),    # fetchrow target
            [_to_record(buy_row)],  # list_trades
            "DELETE 1",             # delete_trade
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/trades/b1")
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
            resp = trades_client.delete("/trades/b1")
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
            resp = trades_client.delete("/trades/b1")
        assert resp.status_code == 400


class TestTradeBulkDelete:
    def test_bulk_delete_empty_ids_422(self, trades_client):
        resp = trades_client.post("/trades/bulk-delete", json={"ids": []})
        assert resp.status_code == 422

    def test_bulk_delete_too_many_ids_422(self, trades_client):
        resp = trades_client.post(
            "/trades/bulk-delete",
            json={"ids": [f"id-{i}" for i in range(201)]},
        )
        assert resp.status_code == 422

    def test_bulk_delete_single_buy_ok(self, trades_client, monkeypatch):
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),         # get_trade_by_id (b1)
            [{"id": "a1", "name": "주식계좌"}],  # repo_list_accounts
            [_to_record(buy_row)],       # list_trades_in_group (group 1)
            "DELETE 1",                  # delete_trade(b1)
        )
        with _patch_trades(conn):
            resp = trades_client.post("/trades/bulk-delete", json={"ids": ["b1"]})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)

    def test_bulk_delete_multi_group_ok(self, trades_client, monkeypatch):
        """서로 다른 그룹 2건 BUY 삭제 — 정렬된 락 순서 + 그룹별 list 호출."""
        sql_calls = _capture_sql(monkeypatch)
        # account_id=a1 / 005930 (삼성전자) — sort key ("a1","KR","005930","삼성전자")
        buy_a = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10,
            account_id="a1", ticker="005930", asset_name="삼성전자",
        )
        # account_id=a1 / 000660 (SK하이닉스) — sort key ("a1","KR","000660","SK하이닉스")
        # → 정렬 시 SK하이닉스 그룹이 먼저 락 획득되어야 한다.
        buy_b = _make_trade_row(
            id_="b2", trade_type="BUY", quantity=5,
            account_id="a1", ticker="000660", asset_name="SK하이닉스",
        )
        conn = FakeConnection(
            _to_record(buy_a),                                # get_trade_by_id(b1)
            _to_record(buy_b),                                # get_trade_by_id(b2)
            [{"id": "a1", "name": "주식계좌"}],                 # repo_list_accounts
            [_to_record(buy_b)],                              # list_trades_in_group (group "000660" — 먼저)
            [_to_record(buy_a)],                              # list_trades_in_group (group "005930")
            "DELETE 1",                                       # delete b2 (group "000660")
            "DELETE 1",                                       # delete b1 (group "005930")
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/bulk-delete", json={"ids": ["b1", "b2"]}
            )
        assert resp.status_code == 204

        # 그룹 단위 list_trades_in_group 가 2회 호출되어야 함.
        list_in_group = [
            q for q in sql_calls
            if "from trades" in q.lower()
            and "user_id = $1" in q.lower()
            and "account_id = $2" in q.lower()
        ]
        assert len(list_in_group) == 2

    def test_bulk_delete_missing_id_404(self, trades_client, monkeypatch):
        """id 중 하나가 None 반환 → 404, DELETE 한 번도 호출되지 않아야 한다."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),  # get_trade_by_id(b1) ok
            None,                  # get_trade_by_id(b2) → None
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/bulk-delete", json={"ids": ["b1", "b2"]}
            )
        assert resp.status_code == 404
        assert "찾을 수 없습니다" in resp.json()["error"]

        deletes = [q for q in sql_calls if q.lower().startswith("delete from trades")]
        assert deletes == []

    def test_bulk_delete_buy_oversell_400(self, trades_client, monkeypatch):
        """그룹에 BUY 10 + SELL 8 일 때 BUY 만 삭제 → 400, DELETE 미실행, 메시지에 계좌·종목·날짜 포함."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1", trade_type="SELL", quantity=8,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                          # get_trade_by_id(b1)
            [{"id": "a1", "name": "주식계좌"}],             # repo_list_accounts
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades_in_group
        )
        with _patch_trades(conn):
            resp = trades_client.post("/trades/bulk-delete", json={"ids": ["b1"]})
        assert resp.status_code == 400
        msg = resp.json()["error"]
        assert "주식계좌" in msg
        assert "삼성전자" in msg
        assert "2024-02-01" in msg
        assert "삭제하지 못했습니다" in msg

        deletes = [q for q in sql_calls if q.lower().startswith("delete from trades")]
        assert deletes == []

    def test_bulk_delete_both_buy_and_sell_ok(self, trades_client):
        """BUY+SELL 둘 다 함께 삭제 → 그룹이 비어 oversell 없음 → 204."""
        buy_row = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1", trade_type="SELL", quantity=8,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                          # get_trade_by_id(b1)
            _to_record(sell_row),                         # get_trade_by_id(s1)
            [{"id": "a1", "name": "주식계좌"}],             # repo_list_accounts
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades_in_group (단일 그룹)
            "DELETE 1",                                   # delete b1
            "DELETE 1",                                   # delete s1
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/trades/bulk-delete", json={"ids": ["b1", "s1"]}
            )
        assert resp.status_code == 204


class TestTradeSummary:
    def test_summary_non_sell_400(self, trades_client):
        row = _make_trade_row(id_="b1", trade_type="BUY")
        conn = FakeConnection(
            _to_record(row),  # sell_row query → BUY trade
            [],               # list_trades (unreached)
        )
        with _patch_trades(conn):
            resp = trades_client.get("/trades/b1/summary")
        assert resp.status_code == 400

    def test_summary_sell_200(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", price=70000, quantity=10,
                                  strategy_type="LONG_TERM",
                                  traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", price=80000, quantity=10,
                                   avg_buy_price=70000.0, profit_loss=100000.0,
                                   holding_days=31,
                                   strategy_type="LONG_TERM",
                                   result="SUCCESS",
                                   traded_at=_dt("2024-02-01T09:00:00+09:00"))

        conn = FakeConnection(
            _to_record(sell_row),
            [_to_record(buy_row), _to_record(sell_row)],
        )
        with _patch_trades(conn):
            resp = trades_client.get("/trades/s1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "pnl" in body
        assert "breakdown" in body
        assert body["pnl"] == 100000.0
        assert body["result"] == "SUCCESS"
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
            resp = trades_client.get("/trades/s1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["holdingDays"] == 0
        assert body["strategyEvaluation"]["holdingDays"] == 0

    def test_summary_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/trades/nonexistent/summary")
        assert resp.status_code == 404


class TestTradesAuth:
    def test_no_token_401(self, auth_client):
        resp = auth_client.get("/trades")
        assert resp.status_code == 401

    def test_invalid_token_401(self, auth_client):
        resp = auth_client.get("/trades", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
