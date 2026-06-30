"""assets 라우터 테스트 — GET /assets/history.

FakeConnection + backfill/quotes mock. 핵심: camelCase 직렬화(asOf), 종목뷰 items(close/qty),
쿼리 파라미터 routing(accountId/ticker/country), 빈 거래 처리.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

from invest_note_api.domain.trade_utils import KST

from invest_note_api.config import Settings, get_settings
from tests.conftest import TEST_USER_ID
from tests.fake_pool import FakeConnection, make_fake_acquire


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _make_trade_row(**kwargs) -> dict:
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
        "traded_at": _dt("2025-06-02T09:00:00+09:00"),
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
        "created_at": _dt("2025-06-01T00:00:00Z"),
        "updated_at": _dt("2025-06-01T00:00:00Z"),
        "account_name": None,
        "account_broker": None,
    }
    base.update(kwargs)
    return base


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


def _patch_assets(conn: FakeConnection):
    return patch("invest_note_api.routers.assets.acquire_for_user", make_fake_acquire(conn))


async def _no_backfill(conn, api_key, tickers, earliest, today, *, country_code="KR", **kw):
    return False


def _closes_today(today_iso: str = "2025-06-03"):
    return [{"ticker": "005930", "close_date": date.fromisoformat("2025-06-02"), "close_price": 75000.0}]


class TestAssetHistory:
    def test_history_forwards_env_providers(self, trades_client):
        """env 공급자 설정이 backfill_closes·fetch_quotes_by_keys 까지 전달 — 죽은 설정 가드."""
        trade = _make_trade_row()
        conn = FakeConnection([_to_record(trade)], _closes_today())
        received: dict = {}

        async def mock_backfill(conn_, api_key, tickers, earliest, today, *, country_code="KR", **kw):
            received["backfill"] = kw
            return False

        async def mock_quotes(state, keys, *, client=None, providers=None, **kw):
            received["providers"] = providers
            return {}

        trades_client.app.dependency_overrides[get_settings] = lambda: Settings(
            supabase_url="https://test.supabase.co",
            quote_providers="yahoo",
            daily_price_gap_provider="none",
        )
        try:
            with _patch_assets(conn):
                with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", mock_backfill):
                    with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                        resp = trades_client.get("/v1/assets/history")
        finally:
            trades_client.app.dependency_overrides.pop(get_settings, None)

        assert resp.status_code == 200
        assert received["providers"] == ["yahoo"]
        assert received["backfill"]["primary_provider"] == "data_go_kr"
        assert received["backfill"]["gap_provider"] == "none"

    def test_account_view_camelcase_and_shape(self, trades_client):
        """계좌뷰: series/items/incomplete/asOf(camelCase), items 에 close/qty 없음."""
        trade = _make_trade_row()
        # responses: [0]=trades(list_trades_with_account), [1]=get_closes (backfill mock 됨).
        conn = FakeConnection([_to_record(trade)], _closes_today())

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": ""}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        body = resp.json()
        # camelCase 계약: asOf (NOT as_of).
        assert "asOf" in body
        assert "as_of" not in body
        assert set(body.keys()) == {
            "series", "items", "incomplete", "asOf", "investedAmount", "usdkrw", "hasForeign"
        }
        # KR-only 스코프: 해외 보유 없음 → usdkrw 미조회(None), hasForeign=False.
        assert body["usdkrw"] is None
        assert body["hasForeign"] is False
        assert body["series"][0] == {"date": "2025-06-02", "value": 10 * 75000}
        # 보유분 매수 원금(cost_basis 합) — 차트 손익 가이드 라인 값.
        assert body["investedAmount"] == 10 * 70000
        # 계좌뷰 items: close/qty 없음.
        assert "close" not in body["items"][0]
        assert "change" in body["items"][0]

    def test_stock_view_includes_close_qty(self, trades_client):
        """종목뷰(?ticker=): items 에 close/qty 포함. 거래는 FakeConnection 이 변환."""
        trade = _make_trade_row()
        conn = FakeConnection([_to_record(trade)], _closes_today())

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": ""}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get(
                        "/v1/assets/history",
                        params={"ticker": "005930", "country": "KR"},
                    )

        assert resp.status_code == 200
        body = resp.json()
        item = body["items"][-1]  # 가장 오래된(6/2).
        assert "close" in item
        assert "qty" in item
        assert item["qty"] == 10.0

    def test_stock_view_routing(self, trades_client):
        """종목뷰: ticker/country 가 list_trades_with_account 로 push."""
        captured: dict = {}

        async def capturing_list(conn_arg, user_id, **kwargs):
            captured.update(kwargs)
            return []

        conn = FakeConnection([])
        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.list_trades_with_account", capturing_list):
                resp = trades_client.get(
                    "/v1/assets/history",
                    params={"ticker": "005930", "country": "KR"},
                )

        assert resp.status_code == 200
        assert captured.get("ticker") == "005930"
        assert captured.get("country") == "KR"

    def test_account_id_routing(self, trades_client):
        """accountId 가 list_trades_with_account 로 전달되고 ticker 는 None(계좌뷰).

        계좌뷰는 country 필터를 push 하지 않는다(country=None) — US/KR 보유를 모두 로드해
        라우터가 country 별로 분리·KRW 환산한다(finding A: 대시보드 합계와 포함범위 일치).
        """
        captured: dict = {}

        async def capturing_list(conn_arg, user_id, **kwargs):
            captured.update(kwargs)
            return []

        conn = FakeConnection([])
        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.list_trades_with_account", capturing_list):
                resp = trades_client.get(
                    "/v1/assets/history",
                    params={"accountId": "a1"},
                )

        assert resp.status_code == 200
        assert captured.get("account_id") == "a1"
        assert captured.get("ticker") is None
        assert captured.get("country") is None

    def test_empty_trades_returns_empty_series(self, trades_client):
        conn = FakeConnection([])
        with _patch_assets(conn):
            resp = trades_client.get("/v1/assets/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["series"] == []
        assert body["items"] == []
        assert body["incomplete"] is False
        assert "asOf" in body
        assert body["investedAmount"] is None

    def test_backfill_incomplete_propagates(self, trades_client):
        """backfill 이 incomplete=True 반환 시 응답 incomplete=True."""
        trade = _make_trade_row()
        conn = FakeConnection([_to_record(trade)], _closes_today())

        async def incomplete_backfill(conn, api_key, tickers, earliest, today, *, country_code="KR", **kw):
            return True

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": ""}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", incomplete_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        assert resp.json()["incomplete"] is True

    def test_holiday_excludes_today_from_series(self, trades_client):
        """휴장일(시세 traded_on ≠ 오늘) → 오늘 점이 series 에 없고 직전 거래일 점은 유지."""
        trade = _make_trade_row()
        conn = FakeConnection([_to_record(trade)], _closes_today())

        async def mock_quotes(state, keys, *, client=None, **kw):
            # 마지막 체결 날짜가 과거 거래일 → 오늘은 휴장.
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": "", "traded_on": "2025-06-02"}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        dates = [p["date"] for p in resp.json()["series"]]
        assert datetime.now(KST).date().isoformat() not in dates
        assert dates == ["2025-06-02"]  # 적재 종가 점은 유지.

    def test_trading_day_includes_today_live_point(self, trades_client):
        """개장일(시세 traded_on == 오늘) → 오늘 점이 라이브 시세로 포함."""
        trade = _make_trade_row()
        conn = FakeConnection([_to_record(trade)], _closes_today())
        today_iso = datetime.now(KST).date().isoformat()

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": "", "traded_on": today_iso}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        series = resp.json()["series"]
        assert series[-1] == {"date": today_iso, "value": 10 * 77000}

    def test_sold_out_invested_amount_none(self, trades_client):
        """전량 매도 → 보유분 없음 → investedAmount=None(FE 단색 차트 폴백)."""
        buy = _make_trade_row()
        sell = _make_trade_row(
            id="t2",
            trade_type="SELL",
            price=75000.0,
            total_amount=750000.0,
            traded_at=_dt("2025-06-03T09:00:00+09:00"),
        )
        conn = FakeConnection([_to_record(buy), _to_record(sell)], _closes_today())

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {"005930:KR": {"price": 77000.0, "currency": "KRW", "as_of": ""}}

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        assert resp.json()["investedAmount"] is None

    def test_mixed_kr_us_krw_summed(self, trades_client):
        """전체뷰 KR+US 혼재: US 를 spot 환산해 같은 KRW 곡선에 합산, hasForeign=True+usdkrw 노출."""
        kr = _make_trade_row()
        us = _make_trade_row(
            id="u1", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
            price=150.0, total_amount=300.0, quantity=2.0,
        )
        kr_closes = [{"ticker": "005930", "close_date": date.fromisoformat("2025-06-02"), "close_price": 70000.0}]
        us_closes = [{"ticker": "AAPL", "close_date": date.fromisoformat("2025-06-02"), "close_price": 200.0}]
        # 응답 순서: [0]=trades, [1]=KR get_closes, [2]=US get_closes (backfill 은 mock).
        conn = FakeConnection([_to_record(kr), _to_record(us)], kr_closes, us_closes)
        today_iso = datetime.now(KST).date().isoformat()

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {
                "005930:KR": {"price": 72000.0, "currency": "KRW", "as_of": "", "traded_on": today_iso},
                "AAPL:US": {"price": 210.0, "currency": "USD", "as_of": "", "traded_on": today_iso},
            }

        async def mock_fx(trades, state, client, *, providers=None, **kw):
            return 1300.0

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    with patch("invest_note_api.routers.assets.usdkrw_if_foreign", mock_fx):
                        resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["usdkrw"] == 1300.0
        assert body["hasForeign"] is True
        # 오늘 점(라이브): KR 10×72000 + US 2×210×1300.
        assert body["series"][-1]["value"] == 10 * 72000 + 2 * 210.0 * 1300.0
        # investedAmount: KR 700000 + US 300×1300.
        assert body["investedAmount"] == 10 * 70000 + 2 * 150.0 * 1300.0

    def test_usdkrw_none_excludes_us_incomplete(self, trades_client):
        """usdkrw=None(환율 미상)+US 보유: US 제외 → KR 만 곡선, incomplete=True, hasForeign=True."""
        kr = _make_trade_row()
        us = _make_trade_row(
            id="u1", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
            price=150.0, total_amount=300.0, quantity=2.0,
        )
        kr_closes = [{"ticker": "005930", "close_date": date.fromisoformat("2025-06-02"), "close_price": 70000.0}]
        us_closes = [{"ticker": "AAPL", "close_date": date.fromisoformat("2025-06-02"), "close_price": 200.0}]
        conn = FakeConnection([_to_record(kr), _to_record(us)], kr_closes, us_closes)
        today_iso = datetime.now(KST).date().isoformat()

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {
                "005930:KR": {"price": 72000.0, "currency": "KRW", "as_of": "", "traded_on": today_iso},
                "AAPL:US": {"price": 210.0, "currency": "USD", "as_of": "", "traded_on": today_iso},
            }

        async def mock_fx(trades, state, client, *, providers=None, **kw):
            return None  # 환율 미상.

        with _patch_assets(conn):
            with patch("invest_note_api.routers.assets.daily_price_seed.backfill_closes", _no_backfill):
                with patch("invest_note_api.routers.assets.fetch_quotes_by_keys", mock_quotes):
                    with patch("invest_note_api.routers.assets.usdkrw_if_foreign", mock_fx):
                        resp = trades_client.get("/v1/assets/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["usdkrw"] is None
        assert body["hasForeign"] is True
        assert body["incomplete"] is True
        # US 제외 → KR 만(10×72000).
        assert body["series"][-1]["value"] == 10 * 72000
        # investedAmount 도 US 제외 → KR 원금만.
        assert body["investedAmount"] == 10 * 70000

    def test_401_without_auth(self, auth_client):
        resp = auth_client.get("/v1/assets/history")
        assert resp.status_code == 401
