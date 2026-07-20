"""trades 라우터 테스트 — FakePool 기반."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import asyncpg
import pytest

from invest_note_api.db_ops.trades_repo import _TRADE_INSERT_PARAM_COUNT
from invest_note_api.schemas.trade import TRADE_FREE_TEXT_MAX_LEN, TradeCreate, TradeUpdate
from tests.conftest import TEST_USER_ID
from tests.fake_pool import FakeConnection, make_fake_acquire


@pytest.fixture(autouse=True)
def staging_store(request, monkeypatch):
    """import 원장 경로를 in-memory 로 대체 — 테스트는 pool=None 이라 실제 DB 불가.

    commit 은 원장(get_ledger_trade_rows)을 읽어 재해소(resolve_tickers)한다. 둘을
    store(batch_id→staging-row dict 리스트) 기반으로 목킹한다. _stage/self._staging_store 로
    거래 행을 직접 주입해 commit 을 검증한다(캡처 우회). preview 는 capture_statement 목킹.
    """
    store: dict[str, dict] = {}

    async def fake_capture(pool, settings, *, user_id, broker_key, filename, content_type, file_bytes):
        from invest_note_api.broker_import import PARSERS
        from invest_note_api.broker_import.base import ParseResult
        from invest_note_api.services.broker_capture import CaptureResult

        parser = PARSERS.get(broker_key)
        pr = parser.parse(file_bytes, filename) if parser else ParseResult()
        return CaptureResult(
            batch_id=str(uuid4()),
            is_new_file=True,
            row_count=len(pr.rows),
            trade_row_count=sum(1 for r in pr.rows if r.kind == "trade"),
            parse_result=pr,
        )

    async def fake_ledger_rows(conn, *, batch_id, user_id):
        entry = store.get(str(batch_id))
        if not entry:
            return []
        out = []
        for i, r in enumerate(entry["rows"], start=1):
            raw_kst = r.get("traded_at_kst_full") or r["traded_at_kst"]
            out.append(
                {
                    "id": uuid4(),
                    "source_row_no": i,
                    "traded_at_raw": raw_kst,
                    "trade_type": r["trade_type"],
                    "asset_name": r["asset_name"],
                    "ticker_hint": r["ticker_symbol"],
                    "isin": None,
                    "country_code": r["country_code"],
                    "quantity": r["quantity"],
                    "price": r["price"],
                    "commission": r.get("commission", 0),
                    "tax": r.get("tax", 0),
                    "exchange_rate": r.get("exchange_rate", 1.0),
                }
            )
        return out

    async def fake_resolve(items, ticker_hints, *, conn, isins, openfigi_api_key):
        # store 의 원래 staging-row 로부터 (country, asset) → {code, exchange} 재구성.
        m: dict = {}
        for entry in store.values():
            for r in entry["rows"]:
                m[(r["country_code"], r["asset_name"])] = {
                    "code": r["ticker_symbol"],
                    "exchange": r.get("exchange", ""),
                }
        return {k: m.get(k) for k in items}

    monkeypatch.setattr("invest_note_api.routers.trades.capture_statement", fake_capture)
    monkeypatch.setattr("invest_note_api.routers.trades.get_ledger_trade_rows", fake_ledger_rows)
    monkeypatch.setattr("invest_note_api.routers.trades.resolve_tickers", fake_resolve)
    if request.instance is not None:
        request.instance._staging_store = store
    return store


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
    custom_tags=None,
    origin="MANUAL",
    name_ko=None,
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
        "custom_tags": custom_tags or [],
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
        "origin": origin,
        "name_ko": name_ko,
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
            resp = trades_client.get("/v1/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert "trades" in body
        assert "accounts" in body

    def test_list_exposes_name_ko(self, trades_client):
        """해외 종목 한글명(name_ko)이 조회 응답에 노출된다 — 표시명 한글 우선용."""
        trade_row = _make_trade_row(
            ticker="AAPL", asset_name="Apple Inc.", country_code="US", name_ko="애플"
        )
        conn = FakeConnection(
            [_to_record(trade_row)],   # list_trades_with_account
            [],                         # accounts
        )
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades")
        assert resp.status_code == 200
        trade = resp.json()["trades"][0]
        assert trade["name_ko"] == "애플"
        assert trade["asset_name"] == "Apple Inc."  # 저장값(영문)은 불변

    def test_list_query_joins_stocks_for_name_ko(self, trades_client, monkeypatch):
        """목록 SQL 이 stocks 를 (country_code, ticker) 로 LEFT JOIN 해 name_ko 를 읽는다."""
        captured: list[str] = []
        orig_fetch = FakeConnection.fetch

        async def spy_fetch(self: Any, query: str, *args: Any) -> list:
            captured.append(query)
            return await orig_fetch(self, query, *args)

        monkeypatch.setattr(FakeConnection, "fetch", spy_fetch)
        conn = FakeConnection([_to_record(_make_trade_row())], [])
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades")
        assert resp.status_code == 200
        join_q = next(
            (q for q in captured if "left join stocks" in q.lower() and "name_ko" in q.lower()),
            None,
        )
        assert join_q is not None, "stocks LEFT JOIN + name_ko 가 목록 쿼리에 없음"
        assert "s.ticker = t.ticker_symbol" in join_q

    def test_list_ticker_filter(self, trades_client):
        trade_row = _make_trade_row()
        conn = FakeConnection(
            [_to_record(trade_row)],
            [],
        )
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades", params={"ticker": "005930", "country": "KR"})
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
            resp = trades_client.get("/v1/trades", params={"ticker": "005930", "country": "KR"})
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
        resp = trades_client.get("/v1/trades", params={"ticker": "/../etc/passwd"})
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
            resp = trades_client.post("/v1/trades", json=self._buy_payload())
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-t1"

    def test_invalid_body_422(self, trades_client):
        resp = trades_client.post("/v1/trades", json={"trade_type": "BUY"})
        assert resp.status_code == 422

    def test_create_future_trade_422(self, trades_client):
        payload = {**self._buy_payload(), "traded_at": "2999-01-10T09:00:00"}
        resp = trades_client.post("/v1/trades", json=payload)
        assert resp.status_code == 422
        assert "미래" in resp.json()["error"]

    def test_create_future_datetime_rejected_by_schema(self):
        payload = {
            **self._buy_payload(),
            "traded_at": datetime(2999, 1, 10, 0, 0, tzinfo=timezone.utc),
        }
        with pytest.raises(ValueError, match="미래"):
            TradeCreate.model_validate(payload)

    def test_create_foreign_buy_allowed(self, trades_client):
        """Phase B: 해외(US) 신규 매수 허용 — 차단 validator 제거됨."""
        acct_row = {"id": "a1"}
        trade_row = _make_trade_row()
        inserted = {"id": "new-us-buy", "trade_type": "BUY"}
        conn = FakeConnection(
            _to_record(acct_row),
            [_to_record(trade_row)],
            _to_record(inserted),
        )
        payload = {
            **self._buy_payload(),
            "asset_name": "Apple",
            "ticker_symbol": "AAPL",
            "country_code": "US",
            "exchange": "NASDAQ",
            "exchange_rate": 1350.0,
        }
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-us-buy"

    def test_create_foreign_buy_without_rate_422(self, trades_client):
        """해외(US) 거래는 거래 시점 환율 필수 — exchange_rate 누락(기본 1.0)이면 거부."""
        payload = {
            **self._buy_payload(),
            "asset_name": "Apple",
            "ticker_symbol": "AAPL",
            "country_code": "US",
            "exchange": "NASDAQ",
        }
        resp = trades_client.post("/v1/trades", json=payload)
        assert resp.status_code == 422
        assert "환율" in resp.json()["error"]

    def test_create_kr_trade_with_exchange_rate_422(self, trades_client):
        """원화(KR) 거래에 1.0 이 아닌 환율 지정은 거부 — 역방향 미러 가드.

        krw_normalized_trade 가 rate != 1.0 이면 무조건 ×rate 라 원가·손익이 조용히 부풀므로
        스키마에서 차단한다(해외 가드의 대칭).
        """
        payload = {**self._buy_payload(), "exchange_rate": 1350.0}
        resp = trades_client.post("/v1/trades", json=payload)
        assert resp.status_code == 422
        assert "환율" in resp.json()["error"]

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
            "exchange_rate": 1350.0,
        }
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades", json=payload)
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
            resp = trades_client.post("/v1/trades", json=payload)
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
            resp = trades_client.post("/v1/trades", json=payload)
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
            resp = trades_client.post("/v1/trades", json=self._buy_payload())
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
            resp = trades_client.post("/v1/trades", json=payload)
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
            resp = trades_client.post("/v1/trades", json=self._buy_payload())
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

        self._staging_store[staging_id] = {
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
                "/v1/trades/import/commit",
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
        self._staging_store[staging_id] = {
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
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
            "custom_tags",
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
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
                "/v1/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 1  # 삼성전자 BUY 만
        assert body["error_count"] == 1
        assert "SK하이닉스" in body["errors"][0]["reason"]

    def test_kr_import_commit_passes_foreign_guard(self, trades_client):
        """KR 거래 import commit 은 해외 환율 방어 가드를 발동하지 않고 정상 INSERT.

        가드(currency != KRW)는 KR 하드코딩 전제를 못박는 방어선 — 현 KR 경로 무회귀 확인.
        """
        staging_id = self._stage(trades_client, [self._merge_row(trade_type="BUY")])
        conn = FakeConnection(
            "a1",
            [],  # list_trades_in_group: 기존 없음
            [_to_record(_make_trade_row(
                id_="new-1", ticker="005930", asset_name="삼성전자", trade_type="BUY",
                traded_at=_dt("2024-01-10T09:00:00+09:00"),
            ))],  # insert RETURNING
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        assert resp.json()["inserted_count"] == 1

    def test_foreign_import_commit_missing_rate_row_error(self, trades_client):
        """US staging row 에 exchange_rate 가 없으면(기본 1.0) 그 행만 commit_error 로 막는다.

        해외 import 도입 후 가드는 배치 전체를 raise 로 중단하지 않고, 환율 누락 행만
        스킵+에러로 처리한다(침묵 통과 금지, 정상 행은 계속 진행).
        """
        us_row = {**self._merge_row(ticker="AAPL", asset_name="Apple", trade_type="BUY"),
                  "country_code": "US"}  # exchange_rate 키 없음 → .get default 1.0
        staging_id = self._stage(trades_client, [us_row])
        conn = FakeConnection("a1", [])  # list_trades_in_group
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 0
        assert body["error_count"] == 1
        assert "환율" in body["errors"][0]["reason"]

    def test_foreign_import_commit_inserts_with_exchange_rate(self, trades_client):
        """exchange_rate 가 실린 US staging row 는 정상 INSERT 되고, 환율이 repo 까지 실려간다.

        inserted_count 만으론 부족 — insert_row 에서 exchange_rate 키가 빠지면 repo default
        1.0 으로 US 거래가 KRW rate 로 INSERT 되어 원가가 ~환율배 부풀지만 count 는 그대로다.
        repo 로 넘어가는 to_insert 의 exchange_rate 까지 단언해 그 회귀를 잠근다.
        """
        us_row = {**self._merge_row(ticker="AAPL", asset_name="Apple", trade_type="BUY"),
                  "country_code": "US", "exchange_rate": 1350.0}
        staging_id = self._stage(trades_client, [us_row])
        conn = FakeConnection(
            "a1",  # assert_account_exists
            [],    # list_trades_in_group
            [_to_record(_make_trade_row(id_="new-1", ticker="AAPL", asset_name="Apple", country_code="US"))],
        )

        from invest_note_api.routers import trades as trades_module

        captured: dict = {}
        real_bulk = trades_module.insert_trades_bulk

        async def spy_bulk(conn_, user_id, to_insert):
            captured["to_insert"] = to_insert
            return await real_bulk(conn_, user_id, to_insert)

        with _patch_trades(conn), patch.object(trades_module, "insert_trades_bulk", spy_bulk):
            resp = trades_client.post(
                "/v1/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_count"] == 1
        assert body["error_count"] == 0
        # 환율이 INSERT 파라미터까지 실려가는가 — 1370배 트랩 가드.
        assert captured["to_insert"][0]["exchange_rate"] == 1350.0
        assert captured["to_insert"][0]["country_code"] == "US"


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
    async def test_new_account_none_uses_empty_holdings(self):
        """account_id=None(신규 계좌) 은 빈 보유 가정으로 file-internal oversell 을 계산한다.

        신규 계좌는 commit 시 빈 계좌로 생성되므로, preview 도 동일하게 무보유 매도를
        제외해야 preview 와 commit 결과가 일치한다("보유0=oversell 불가" 오판 회귀 가드).
        DB 접근이 없어야 하므로 acquire_for_user 를 패치하지 않는다(호출되면 예외).
        """
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [self._row(trade_type="SELL")]
        errors, excluded_count = await _validate_import_groups(
            pool=None, user_id=TEST_USER_ID, account_id=None, rows=rows,
        )
        assert len(errors) == 1
        assert "보유 수량이 없습니다" in errors[0].reason
        assert excluded_count == 1

    @pytest.mark.asyncio
    async def test_new_account_none_buy_and_sell_pass(self):
        """account_id=None 이어도 file 내 BUY 가 SELL 을 커버하면 통과(빈 보유 + 파일 매수)."""
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [
            self._row(trade_type="BUY", quantity=1),
            self._row(trade_type="SELL", quantity=1, traded_at_kst="2024-01-11"),
        ]
        errors, excluded_count = await _validate_import_groups(
            pool=None, user_id=TEST_USER_ID, account_id=None, rows=rows,
        )
        assert errors == []
        assert excluded_count == 0

    @pytest.mark.asyncio
    async def test_excluded_count_omits_dup_rows_to_avoid_double_subtraction(self):
        """제외 그룹 안의 dup 행은 excluded_count 에서 빠진다(신규 행만 카운트).

        회귀 가드: new_count = staged - dup 라서, 제외 그룹의 dup 까지 excluded 로 세면
        FE effectiveNewCount(=new_count - excluded)가 그 dup 을 이중 차감해 commit inserted
        보다 적게 나온다(기존 계좌 재업로드 시 발현). 여기선 dup BUY 1 + 신규 SELL 1(oversell)
        그룹이므로 excluded 는 2가 아니라 1(SELL 만)이어야 한다.
        """
        from invest_note_api.routers.trades import _validate_import_groups

        rows = [
            self._row(trade_type="BUY", quantity=10, price=70000, traded_at_kst="2024-01-10"),
            self._row(trade_type="SELL", quantity=100, price=80000, traded_at_kst="2024-01-20"),
        ]
        # 계좌에 파일 첫 행(BUY 10@70000 2024-01-10)과 동일한 거래가 이미 있음 → dup.
        existing = _to_record(_make_trade_row(
            id_="existing-buy", trade_type="BUY", ticker="005930", asset_name="삼성전자",
            quantity=10, price=70000, traded_at=_dt("2024-01-10T09:00:00+09:00"),
        ))
        conn = FakeConnection("a1", [existing])
        with patch(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(conn),
        ):
            errors, excluded_count = await _validate_import_groups(
                pool=None, user_id=TEST_USER_ID, account_id="a1", rows=rows,
            )
        assert len(errors) == 1
        assert "초과" in errors[0].reason
        assert excluded_count == 1  # dup BUY 제외, 신규 SELL 만 카운트

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


class TestImportCommitExchange:
    """회귀: commit 물질화 시 resolve 로 채운 exchange 가 trades INSERT 까지 실려야 한다.

    과거엔 라우터가 exchange 를 ''로 하드코딩해 import 거래의 exchange 가 빈 값이 되던 버그가
    있었다. rewire 후엔 원장→commit 재해소 경로가 exchange 를 insert_row 로 나른다.
    (resolve_tickers 자체의 stocks 매칭은 ticker_resolver 단위 테스트가 커버.)
    """

    def _commit_capture_insert(self, trades_client, *, ticker, exchange) -> dict:
        sid = str(uuid4())
        self._staging_store[sid] = {
            "user_id": TEST_USER_ID,
            "rows": [{
                "asset_name": "삼성전자",
                "ticker_symbol": ticker,
                "market_type": "STOCK",
                "trade_type": "BUY",
                "price": 70000,
                "quantity": 10,
                "traded_at_kst": "2024-01-10",
                "traded_at_kst_full": None,
                "commission": 0,
                "tax": 0,
                "country_code": "KR",
                "exchange": exchange,  # fake_resolve 가 이 값을 code/exchange 로 되돌린다
            }],
        }
        conn = FakeConnection(
            "a1",  # assert_account_exists
            [],    # list_trades_in_group
            [_to_record(_make_trade_row(id_="new-1", ticker=ticker, exchange=exchange))],
        )
        from invest_note_api.routers import trades as trades_module

        captured: dict = {}
        real_bulk = trades_module.insert_trades_bulk

        async def spy_bulk(conn_, user_id, to_insert):
            captured["to_insert"] = to_insert
            return await real_bulk(conn_, user_id, to_insert)

        with _patch_trades(conn), patch.object(
            trades_module, "insert_trades_bulk", spy_bulk
        ):
            resp = trades_client.post(
                "/v1/trades/import/commit",
                json={"staging_id": sid, "account_id": "a1"},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["inserted_count"] == 1
        return captured["to_insert"][0]

    def test_resolved_exchange_flows_to_insert(self, trades_client):
        insert = self._commit_capture_insert(trades_client, ticker="005930", exchange="KOSPI")
        assert insert["exchange"] == "KOSPI"

    def test_hinted_ticker_still_carries_exchange(self, trades_client):
        # 파일에 코드(hint=ticker)가 박혀 있어도 exchange 는 resolve 결과로 채워 INSERT.
        insert = self._commit_capture_insert(trades_client, ticker="005930", exchange="KOSDAQ")
        assert insert["ticker_symbol"] == "005930"
        assert insert["exchange"] == "KOSDAQ"


class TestGetTrade:
    def test_get_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/nonexistent")
        assert resp.status_code == 404

    def test_get_200(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(_to_record(row))
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/t1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "t1"


class TestPatchTrade:
    def test_empty_body_204(self, trades_client):
        # No acquire call needed — returns 204 before DB
        resp = trades_client.patch("/v1/trades/t1", json={})
        assert resp.status_code == 204

    def test_patch_non_pnl_field(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"buy_reason": "테스트"})
        assert resp.status_code == 204

    def test_patch_free_text_5000_chars_ok(self, trades_client):
        row = _make_trade_row()
        conn = FakeConnection(
            _to_record(row),  # existing trade
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch(
                "/v1/trades/t1",
                json={"buy_reason": "가" * TRADE_FREE_TEXT_MAX_LEN},
            )
        assert resp.status_code == 204

    def test_patch_free_text_5001_chars_422(self, trades_client):
        resp = trades_client.patch(
            "/v1/trades/t1",
            json={"buy_reason": "가" * (TRADE_FREE_TEXT_MAX_LEN + 1)},
        )
        assert resp.status_code == 422
        assert "5000" in resp.json()["error"]

    def test_patch_not_found_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow returns None
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/nonexistent", json={"price": 75000})
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
            resp = trades_client.patch("/v1/trades/t1", json={"price": 75000})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        _assert_lock_timeout_before_lock(sql_calls)

    def test_patch_sell_emotion_only_ignored(self, trades_client, monkeypatch):
        """SELL의 emotion 단독 patch는 무시되어야 한다 — 자동 산출 정책."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))  # fetchrow만 호출, UPDATE 없음
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/s1", json={"emotion": "FOMO"})
        assert resp.status_code == 204
        # patch_trade의 SET 쿼리가 호출되지 않아야 함
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_sell_reasoning_tags_only_ignored(self, trades_client, monkeypatch):
        """SELL의 reasoning_tags 단독 patch도 무시."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/s1", json={"reasoning_tags": ["TECHNICAL"]})
        assert resp.status_code == 204
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_sell_custom_tags_only_ignored(self, trades_client, monkeypatch):
        """SELL의 custom_tags 단독 patch도 무시 — 매수에서 자동 상속되는 필드."""
        sql_calls = _capture_sql(monkeypatch)
        sell_row = _make_trade_row(id_="s1", trade_type="SELL", quantity=10)
        conn = FakeConnection(_to_record(sell_row))
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/s1", json={"custom_tags": ["배당"]})
        assert resp.status_code == 204
        assert not any("UPDATE trades SET" in q for q in sql_calls)

    def test_patch_buy_custom_tags_recalculates_matched_sell(self, trades_client, monkeypatch):
        """BUY custom_tags 수정은 매칭 SELL의 자동 상속 custom_tags 재계산을 트리거해야 함."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1", trade_type="SELL", quantity=10,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                          # existing fetchrow
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades (PNL 분기)
            "UPDATE 1",                                   # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/b1", json={"custom_tags": ["테마주"]})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        # recalc UPDATE 에 custom_tags = $6 컬럼이 포함되어야 함(SELL 자동 상속).
        assert any(
            "custom_tags = $6" in q and "UPDATE trades SET profit_loss" in q
            for q in sql_calls
        )

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
                "/v1/trades/s1",
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
            resp = trades_client.patch("/v1/trades/b1", json={"strategy_type": "LONG_TERM"})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        assert any(
            "strategy_type = $4" in q and "UPDATE trades SET profit_loss" in q
            for q in sql_calls
        )

    def test_patch_us_trade_exchange_rate_1_rejected(self, trades_client):
        """해외(US) 거래를 exchange_rate=1.0 으로 패치하면 거부 — create 와 대칭 가드."""
        row = _make_trade_row(country_code="US")
        row["exchange_rate"] = 1350.0
        conn = FakeConnection(_to_record(row))  # fetchrow만 — 가드에서 거부
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"exchange_rate": 1.0})
        assert resp.status_code == 400
        assert "환율" in resp.json()["error"]

    def test_patch_us_trade_valid_exchange_rate_ok(self, trades_client):
        """해외(US) 거래를 유효 환율(1350)로 패치하면 성공."""
        row = _make_trade_row(country_code="US")
        row["exchange_rate"] = 1350.0
        conn = FakeConnection(
            _to_record(row),    # existing fetchrow
            [_to_record(row)],  # list_trades (PNL 분기 — exchange_rate 는 pnl_affecting)
            "UPDATE 1",         # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"exchange_rate": 1350.0})
        assert resp.status_code == 204

    def test_patch_kr_trade_exchange_rate_1_ok(self, trades_client):
        """KR 거래는 exchange_rate=1.0 패치가 정상(가드 무관)."""
        row = _make_trade_row(country_code="KR")
        row["exchange_rate"] = 1.0
        conn = FakeConnection(
            _to_record(row),    # existing fetchrow
            [_to_record(row)],  # list_trades
            "UPDATE 1",         # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"exchange_rate": 1.0})
        assert resp.status_code == 204

    def test_patch_kr_trade_nondefault_exchange_rate_rejected(self, trades_client):
        """원화(KR) 거래에 1.0 이 아닌 환율 패치는 거부 — create 역방향 가드와 대칭."""
        row = _make_trade_row(country_code="KR")
        row["exchange_rate"] = 1.0
        conn = FakeConnection(_to_record(row))  # fetchrow만 — 가드에서 거부
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"exchange_rate": 1350.0})
        assert resp.status_code == 400
        assert "환율" in resp.json()["error"]

    def test_patch_us_trade_without_exchange_rate_ok(self, trades_client):
        """exchange_rate 미포함 패치(다른 필드만)는 US 거래여도 성공 — 가드 미발동."""
        row = _make_trade_row(country_code="US")
        row["exchange_rate"] = 1350.0
        conn = FakeConnection(
            _to_record(row),  # fetchrow — buy_reason 은 비-PNL 필드라 list_trades 없음
            "UPDATE 1",       # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"buy_reason": "메모"})
        assert resp.status_code == 204


def _capture_insert_params(monkeypatch) -> list[tuple]:
    """trades INSERT 의 실제 파라미터를 행 단위로 기록 — origin 분기 검증용.

    create 경로는 conn.fetchrow(INSERT ... RETURNING, *params) (1행),
    import 경로는 conn.fetch(INSERT ... VALUES (...),(...) RETURNING *, *flattened)
    로 다중 행을 평탄화해 보낸다. 두 경로 모두 _TRADE_INSERT_PARAM_COUNT(=22)
    단위로 청크해 행 튜플 리스트로 환원한다.
    """
    rows: list[tuple] = []
    n = _TRADE_INSERT_PARAM_COUNT
    orig_fetchrow = FakeConnection.fetchrow
    orig_fetch = FakeConnection.fetch

    def _collect(query: str, args: tuple) -> None:
        if "insert into trades" in query.lower():
            rows.extend(args[i : i + n] for i in range(0, len(args), n))

    async def spy_fetchrow(self: Any, query: str, *args: Any) -> Any:
        _collect(query, args)
        return await orig_fetchrow(self, query, *args)

    async def spy_fetch(self: Any, query: str, *args: Any) -> Any:
        _collect(query, args)
        return await orig_fetch(self, query, *args)

    monkeypatch.setattr(FakeConnection, "fetchrow", spy_fetchrow)
    monkeypatch.setattr(FakeConnection, "fetch", spy_fetch)
    return rows


class TestTradeOrigin:
    """origin INSERT 분기 + IMPORT 거래 금액 잠금 가드 (Task #13/#14)."""

    # ── INSERT 분기 (마지막 INSERT 파라미터 = origin) ─────────────────────────

    def test_create_inserts_origin_manual(self, trades_client, monkeypatch):
        """개별등록 POST /trades 는 origin=MANUAL 로 INSERT 한다."""
        params = _capture_insert_params(monkeypatch)
        conn = FakeConnection(
            _to_record({"id": "a1"}),                       # account exists
            [_to_record(_make_trade_row())],                # list_trades
            _to_record({"id": "new-t1", "trade_type": "BUY"}),  # insert RETURNING
        )
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades", json=TestCreateTrade()._buy_payload())
        assert resp.status_code == 201
        assert len(params) == 1
        # origin 은 끝에서 2번째(마지막은 source_ledger_entry_id), 개별등록은 None.
        assert params[0][-2] == "MANUAL"
        assert params[0][-1] is None

    def test_import_commit_inserts_origin_import(self, trades_client, monkeypatch):
        """거래내역서 일괄등록 commit 은 origin=IMPORT 로 INSERT 한다."""
        params = _capture_insert_params(monkeypatch)
        staging_id = str(uuid4())
        self._staging_store[staging_id] = {
            "user_id": TEST_USER_ID,
            "rows": [
                TestImportCommit()._staged_row("005930", "삼성전자"),
                TestImportCommit()._staged_row("000660", "SK하이닉스"),
            ],
            "parse_errors": [],
            "usd_skip_count": 0,
            "broker_key": "toss",
            "account_hint": None,
        }
        conn = FakeConnection(
            "a1",                                            # assert_account_exists
            [],                                              # group1 list_trades_in_group
            [_to_record(_make_trade_row(id_="new-1", ticker="005930", asset_name="삼성전자"))],
            [],                                              # group2 list_trades_in_group
            [_to_record(_make_trade_row(id_="new-2", ticker="000660", asset_name="SK하이닉스"))],
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/import/commit",
                json={"staging_id": staging_id, "account_id": "a1"},
            )
        assert resp.status_code == 200
        assert len(params) == 2
        # origin(끝에서 2번째) = IMPORT, 마지막 = source_ledger_entry_id(원장 행 id, 非 None).
        assert all(p[-2] == "IMPORT" for p in params)
        assert all(p[-1] is not None for p in params)

    # ── GET 응답에 origin 노출 (FE 배지/잠금이 의존하는 shape) ─────────────────

    def test_list_response_exposes_origin(self, trades_client):
        """GET /trades(목록) 응답의 각 trade 에 origin 이 실제 직렬화된다."""
        conn = FakeConnection(
            [_to_record(_make_trade_row(origin="IMPORT"))],  # list_trades_with_account
            [],                                              # accounts
        )
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades")
        assert resp.status_code == 200
        assert resp.json()["trades"][0]["origin"] == "IMPORT"

    def test_detail_response_exposes_origin(self, trades_client):
        """GET /trades/{id}(상세) 응답에 origin 이 실제 직렬화된다."""
        conn = FakeConnection(_to_record(_make_trade_row(origin="IMPORT")))
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/t1")
        assert resp.status_code == 200
        assert resp.json()["origin"] == "IMPORT"

    # ── PATCH 잠금 가드 (IMPORT 거래의 금액 5필드) ────────────────────────────

    @pytest.mark.parametrize(
        "field,value",
        [
            ("price", 75000),
            ("quantity", 5),
            ("exchange_rate", 1350),
            ("commission", 100),
            ("tax", 50),
        ],
    )
    def test_patch_import_locked_field_422(self, trades_client, field, value):
        """IMPORT 거래에 금액 5필드 중 하나라도 PATCH → 422 (DB 미접근)."""
        row = _make_trade_row(origin="IMPORT")
        conn = FakeConnection(_to_record(row))  # fetchrow 만 — 가드에서 즉시 차단
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={field: value})
        assert resp.status_code == 422
        assert "금액 정보를 수정할 수 없어요" in resp.json()["error"]

    def test_patch_import_explicit_null_locked_field_422(self, trades_client):
        """명시적 price=null 도 model_fields_set 에 포함되어 거부된다."""
        row = _make_trade_row(origin="IMPORT")
        conn = FakeConnection(_to_record(row))
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"price": None})
        assert resp.status_code == 422

    # ── PATCH 메타 허용 (IMPORT 거래여도 분석 메타는 수정 가능) ────────────────

    def test_patch_import_meta_allowed(self, trades_client):
        """IMPORT 거래의 비-금액 메타(buy_reason)는 그대로 수정 허용 → 204."""
        row = _make_trade_row(origin="IMPORT")
        conn = FakeConnection(
            _to_record(row),  # fetchrow
            "UPDATE 1",       # patch_trade (비-PNL 메타라 list_trades 없음)
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"buy_reason": "저점 매수 판단"})
        assert resp.status_code == 204

    def test_patch_import_meta_with_market_type_not_false_rejected(self, trades_client):
        """드리프트 가드: IMPORT 거래에 메타+market_type 동봉 PATCH → 422 아님(204).

        FE 는 메타 수정 시 market_type 을 변경 없이 항상 전송한다. market_type 이
        잠금 집합에 끼면 메타 수정까지 false-reject 되므로, 절대 422 가 아니어야 한다.
        """
        row = _make_trade_row(origin="IMPORT")
        conn = FakeConnection(
            _to_record(row),  # fetchrow
            "UPDATE 1",       # patch_trade (market_type/buy_reason 둘 다 비-PNL)
        )
        with _patch_trades(conn):
            resp = trades_client.patch(
                "/v1/trades/t1",
                json={"buy_reason": "메모", "market_type": "STOCK"},
            )
        assert resp.status_code == 204

    def test_patch_import_buy_meta_cascades_to_sell(self, trades_client, monkeypatch):
        """IMPORT BUY 의 메타(custom_tags) 수정도 매칭 SELL 캐스케이드를 트리거한다."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(
            id_="b1", trade_type="BUY", quantity=10, origin="IMPORT",
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell_row = _make_trade_row(
            id_="s1", trade_type="SELL", quantity=10, origin="IMPORT",
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        conn = FakeConnection(
            _to_record(buy_row),                          # existing fetchrow
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades (PNL 분기)
            "UPDATE 1",                                   # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/b1", json={"custom_tags": ["테마주"]})
        assert resp.status_code == 204
        _assert_lock_before_list(sql_calls)
        assert any(
            "custom_tags = $6" in q and "UPDATE trades SET profit_loss" in q
            for q in sql_calls
        )

    # ── 회귀: MANUAL 거래는 금액 PATCH 기존대로 허용 ──────────────────────────

    def test_patch_manual_locked_field_ok(self, trades_client, monkeypatch):
        """MANUAL 거래의 금액(price) PATCH 는 기존대로 허용 → 204 (회귀 없음)."""
        row = _make_trade_row(origin="MANUAL")
        conn = FakeConnection(
            _to_record(row),    # existing fetchrow
            [_to_record(row)],  # list_trades (PNL 분기)
            "UPDATE 1",         # patch_trade
        )
        with _patch_trades(conn):
            resp = trades_client.patch("/v1/trades/t1", json={"price": 75000})
        assert resp.status_code == 204

    # ── origin 불변 (PATCH 화이트리스트 미포함) ───────────────────────────────

    def test_origin_not_patchable_via_schema(self):
        """origin 은 TradeUpdate 스키마에 없어 PATCH 로 변경 불가(불변)."""
        assert "origin" not in TradeUpdate.model_fields


class TestCustomTagsRegistry:
    def test_list_shape(self, trades_client):
        """GET /trades/custom-tags 응답은 {tags: [{id, label}]} — FE 계약 잠금."""
        conn = FakeConnection([
            {"id": "11111111-1111-1111-1111-111111111111", "label": "배당"},
            {"id": "22222222-2222-2222-2222-222222222222", "label": "테마주"},
        ])
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/custom-tags")
        assert resp.status_code == 200
        assert resp.json() == {"tags": [
            {"id": "11111111-1111-1111-1111-111111111111", "label": "배당"},
            {"id": "22222222-2222-2222-2222-222222222222", "label": "테마주"},
        ]}

    def test_list_empty(self, trades_client):
        conn = FakeConnection([])
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/custom-tags")
        assert resp.status_code == 200
        assert resp.json() == {"tags": []}

    def test_create_returns_id_label(self, trades_client):
        """POST /trades/custom-tags → {id, label}, 201."""
        conn = FakeConnection({"id": "33333333-3333-3333-3333-333333333333", "label": "배당"})
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades/custom-tags", json={"label": "  배당 "})
        assert resp.status_code == 201
        assert resp.json() == {"id": "33333333-3333-3333-3333-333333333333", "label": "배당"}

    def test_create_blank_label_422(self, trades_client):
        resp = trades_client.post("/v1/trades/custom-tags", json={"label": "   "})
        assert resp.status_code == 422

    def test_create_too_long_422(self, trades_client):
        resp = trades_client.post("/v1/trades/custom-tags", json={"label": "x" * 21})
        assert resp.status_code == 422

    def test_delete_ok(self, trades_client):
        conn = FakeConnection("DELETE 1")
        with _patch_trades(conn):
            resp = trades_client.delete("/v1/trades/custom-tags/33333333-3333-3333-3333-333333333333")
        assert resp.status_code == 204

    def test_delete_not_found_404(self, trades_client):
        conn = FakeConnection("DELETE 0")
        with _patch_trades(conn):
            resp = trades_client.delete("/v1/trades/custom-tags/33333333-3333-3333-3333-333333333333")
        assert resp.status_code == 404


class TestCustomTagsNormalization:
    """TradeUpdate.custom_tags 정규화 validator — trim/빈값/중복/길이/개수."""

    def test_trim_dedupe_drop_empty(self):
        u = TradeUpdate(custom_tags=["  배당 ", "배당", "", "테마주", "  "])
        assert u.custom_tags == ["배당", "테마주"]

    def test_none_passthrough(self):
        assert TradeUpdate(custom_tags=None).custom_tags is None

    def test_tag_too_long_rejected(self):
        with pytest.raises(ValueError):
            TradeUpdate(custom_tags=["x" * 21])

    def test_too_many_tags_rejected(self):
        with pytest.raises(ValueError):
            TradeUpdate(custom_tags=[f"태그{i}" for i in range(11)])


class TestDeleteTrade:
    def test_delete_404(self, trades_client):
        conn = FakeConnection(None)  # fetchrow → None → 404
        with _patch_trades(conn):
            resp = trades_client.delete("/v1/trades/nonexistent")
        assert resp.status_code == 404

    def test_delete_buy_ok(self, trades_client):
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            _to_record(buy_row),    # fetchrow target
            [_to_record(buy_row)],  # list_trades
            "DELETE 1",             # delete_trade
        )
        with _patch_trades(conn):
            resp = trades_client.delete("/v1/trades/b1")
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
            resp = trades_client.delete("/v1/trades/b1")
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
            resp = trades_client.delete("/v1/trades/b1")
        assert resp.status_code == 400


class TestTradeBulkDelete:
    def test_bulk_delete_empty_ids_422(self, trades_client):
        resp = trades_client.post("/v1/trades/bulk-delete", json={"ids": []})
        assert resp.status_code == 422

    def test_bulk_delete_too_many_ids_422(self, trades_client):
        resp = trades_client.post(
            "/v1/trades/bulk-delete",
            json={"ids": [f"id-{i}" for i in range(201)]},
        )
        assert resp.status_code == 422

    def test_bulk_delete_single_buy_ok(self, trades_client, monkeypatch):
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            [_to_record(buy_row)],       # list_trades_by_ids (b1)
            [{"id": "a1", "name": "주식계좌"}],  # repo_list_accounts
            [_to_record(buy_row)],       # list_trades_in_group (group 1)
            "DELETE 1",                  # delete_trades_by_ids
        )
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades/bulk-delete", json={"ids": ["b1"]})
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
            [_to_record(buy_a), _to_record(buy_b)],           # list_trades_by_ids(b1, b2)
            [{"id": "a1", "name": "주식계좌"}],                 # repo_list_accounts
            [_to_record(buy_b)],                              # list_trades_in_group (group "000660" — 먼저)
            [_to_record(buy_a)],                              # list_trades_in_group (group "005930")
            "DELETE 2",                                       # delete_trades_by_ids (전체 단일 쿼리)
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/bulk-delete", json={"ids": ["b1", "b2"]}
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
        """조회 결과 개수가 요청보다 적으면 → 404, DELETE 한 번도 호출되지 않아야 한다."""
        sql_calls = _capture_sql(monkeypatch)
        buy_row = _make_trade_row(id_="b1", trade_type="BUY", quantity=10)
        conn = FakeConnection(
            [_to_record(buy_row)],  # list_trades_by_ids → b1 만 반환 (b2 누락)
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/bulk-delete", json={"ids": ["b1", "b2"]}
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
            [_to_record(buy_row)],                        # list_trades_by_ids(b1)
            [{"id": "a1", "name": "주식계좌"}],             # repo_list_accounts
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades_in_group
        )
        with _patch_trades(conn):
            resp = trades_client.post("/v1/trades/bulk-delete", json={"ids": ["b1"]})
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
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades_by_ids(b1, s1)
            [{"id": "a1", "name": "주식계좌"}],             # repo_list_accounts
            [_to_record(buy_row), _to_record(sell_row)],  # list_trades_in_group (단일 그룹)
            "DELETE 2",                                   # delete_trades_by_ids
        )
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/bulk-delete", json={"ids": ["b1", "s1"]}
            )
        assert resp.status_code == 204

    def test_bulk_delete_malformed_uuid_422(self, trades_client, monkeypatch):
        """malformed UUID 가 들어오면 asyncpg 예외가 500 으로 새지 않고 422 로 떨어진다."""
        import asyncpg

        async def raise_invalid_uuid(*args, **kwargs):
            raise asyncpg.exceptions.InvalidTextRepresentationError(
                'invalid input syntax for type uuid: "not-a-uuid"'
            )

        monkeypatch.setattr(
            "invest_note_api.routers.trades.list_trades_by_ids",
            raise_invalid_uuid,
        )
        # acquire_for_user 만 통과시키면 됨 — list_trades_by_ids 가 raise 하므로 conn 미사용.
        conn = FakeConnection()
        with _patch_trades(conn):
            resp = trades_client.post(
                "/v1/trades/bulk-delete", json={"ids": ["not-a-uuid"]}
            )
        assert resp.status_code == 422
        assert "올바르지" in resp.json()["error"]


class TestTradeSummary:
    def test_summary_non_sell_400(self, trades_client):
        row = _make_trade_row(id_="b1", trade_type="BUY")
        conn = FakeConnection(
            _to_record(row),  # sell_row query → BUY trade
            [],               # list_trades (unreached)
        )
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/b1/summary")
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
            resp = trades_client.get("/v1/trades/s1/summary")
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
            resp = trades_client.get("/v1/trades/s1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["holdingDays"] == 0
        assert body["strategyEvaluation"]["holdingDays"] == 0

    def test_summary_404(self, trades_client):
        conn = FakeConnection(None)
        with _patch_trades(conn):
            resp = trades_client.get("/v1/trades/nonexistent/summary")
        assert resp.status_code == 404


class TestTradesAuth:
    def test_no_token_401(self, auth_client):
        resp = auth_client.get("/v1/trades")
        assert resp.status_code == 401

    def test_invalid_token_401(self, auth_client):
        resp = auth_client.get("/v1/trades", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
