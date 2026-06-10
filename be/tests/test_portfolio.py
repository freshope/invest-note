"""portfolio 라우터 테스트 — FakePool + quote mock."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch


from invest_note_api.config import Settings, get_settings
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
        "exchange_rate": 1.0,
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
                "/portfolio/holding",
                params={"accountId": "a1", "assetName": "삼성전자", "ticker": "005930", "country": "KR"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["quantity"] == 10.0

    def test_holding_missing_params_400(self, trades_client):
        resp = trades_client.get("/portfolio/holding")
        assert resp.status_code == 422  # FastAPI validation error for missing required params

    def test_no_holding_zero(self, trades_client):
        conn = FakeConnection([])
        with _patch_portfolio(conn):
            resp = trades_client.get(
                "/portfolio/holding",
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

        async def mock_quotes(state, keys, **kw):
            return {}

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                resp = trades_client.get("/portfolio/summary")

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

    def test_summary_us_position_converts_to_krw(self, trades_client):
        """US 포지션이 라우터를 통과 — 원가는 거래시점 환율로 KRW 고정, 평가액은 현재 환율.

        라우터 fx 와이어링(게이트+DI+fetch_usdkrw)을 검증. cost_basis 는 KRW 고정,
        evaluation 은 현재 환율 환산, evaluation_native 는 USD 보조.
        """
        # US BUY $200×10 @1300(거래시점) → 원가 2,600,000 KRW 고정.
        trade = _make_trade_row(
            asset_name="Apple", ticker_symbol="AAPL", country_code="US",
            exchange="NASDAQ", price=200.0, quantity=10.0, exchange_rate=1300.0,
        )
        account = _make_account_row()
        conn = FakeConnection([_to_record(trade)], [_to_record(account)])

        async def mock_quotes(state, keys, **kw):
            return {"AAPL:US": {"price": 220.0, "currency": "USD", "as_of": ""}}

        async def mock_fx(trades, state, client, *, force_refresh=False):
            return 1500.0  # 현재 USD/KRW

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                with patch("invest_note_api.routers.portfolio.usdkrw_if_foreign", mock_fx):
                    resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        pos = body["positions"][0]
        assert pos["costBasis"] == 2_600_000.0       # 거래시점 환율로 KRW 고정
        assert pos["costBasisNative"] == 2000.0      # USD ($200×10)
        assert pos["evaluation"] == 3_300_000.0      # 220×10×1500(현재환율)
        assert pos["evaluationNative"] == 2200.0     # USD
        assert pos["currency"] == "USD"
        # 총액(KRW): 평가 3,300,000
        assert body["totals"]["totalEvaluation"] == 3_300_000.0
        assert body["totals"]["missingQuoteTickers"] == []

    def test_summary_us_position_excluded_when_fx_unavailable(self, trades_client):
        """현재 환율 조회 실패(None) → US 평가액 KRW 미상(missing). 원가는 KRW 고정 유지."""
        trade = _make_trade_row(
            asset_name="Apple", ticker_symbol="AAPL", country_code="US",
            exchange="NASDAQ", price=200.0, quantity=10.0, exchange_rate=1300.0,
        )
        account = _make_account_row()
        conn = FakeConnection([_to_record(trade)], [_to_record(account)])

        async def mock_quotes(state, keys, **kw):
            return {"AAPL:US": {"price": 120.0, "currency": "USD", "as_of": ""}}

        async def mock_fx(trades, state, client, *, force_refresh=False):
            return None  # 환율 못 받음

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                with patch("invest_note_api.routers.portfolio.usdkrw_if_foreign", mock_fx):
                    resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        assert body["totals"]["totalEvaluation"] == 0.0
        assert "Apple" in body["totals"]["missingQuoteTickers"]

    def test_summary_default_includes_holdings(self, trades_client):
        """파라미터 미전송(default withQuotes=true) → 기존 시세 동작 유지 + holdings additive 필드 존재."""
        trade = _make_trade_row()
        account = _make_account_row()

        conn = FakeConnection(
            [_to_record(trade)],
            [_to_record(account)],
        )

        async def mock_quotes(state, keys, *, client=None, force_refresh=False, **kw):
            return {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": ""}}

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        # 기존 시세 동작 유지 (현재가 채워짐)
        assert body["positions"][0]["currentPrice"] == 75000.0
        # additive 계약: snapshots[].holdings 존재 + key/quantity 일치
        snap = body["snapshots"][0]
        assert "holdings" in snap
        assert snap["holdings"] == [{"key": "005930:KR", "quantity": 10.0}]

    def test_summary_forwards_env_providers(self, trades_client):
        """QUOTE_PROVIDERS env 가 fetch_quotes_by_keys providers 로 전달 — 죽은 설정 가드."""
        trade = _make_trade_row()
        account = _make_account_row()
        conn = FakeConnection([_to_record(trade)], [_to_record(account)])
        received: dict = {}

        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None, **kw):
            received["providers"] = providers
            return {}

        trades_client.app.dependency_overrides[get_settings] = lambda: Settings(
            supabase_url="https://test.supabase.co", quote_providers="yahoo"
        )
        try:
            with _patch_portfolio(conn):
                with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/portfolio/summary")
        finally:
            trades_client.app.dependency_overrides.pop(get_settings, None)

        assert resp.status_code == 200
        assert received["providers"] == ["yahoo"]

    def test_summary_with_quotes_false_skips_fetch(self, trades_client):
        """withQuotes=false → fetch_quotes_by_keys 미호출, positions 가격 null, holdings 채워짐, totals 현금 기준."""
        trade = _make_trade_row()
        account = _make_account_row()

        conn = FakeConnection(
            [_to_record(trade)],
            [_to_record(account)],
        )

        called = {"hit": False}

        async def must_not_call(state, keys, *, client=None, force_refresh=False, **kw):
            called["hit"] = True
            return {"005930:KR": {"price": 99999.0, "currency": "KRW", "as_of": ""}}

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", must_not_call):
                resp = trades_client.get(
                    "/portfolio/summary", params={"withQuotes": "false"}
                )

        assert resp.status_code == 200
        assert called["hit"] is False, "withQuotes=false 인데 시세 fetch 가 호출됨"
        body = resp.json()
        # 시세 의존 값은 null/0
        pos = body["positions"][0]
        assert pos["currentPrice"] is None
        assert pos["evaluation"] is None
        assert pos["unrealizedPnL"] is None
        # 시세 비의존 값은 그대로 (수량/원가)
        assert pos["holdingQuantity"] == 10.0
        totals = body["totals"]
        assert totals["totalEvaluation"] == 0.0
        assert totals["totalAssets"] == totals["totalCash"]  # 현금 기준
        # holdings 는 채워짐 + 계좌 snapshot 의 stockEvaluation/totalValue 는 현금 기준
        snap = body["snapshots"][0]
        assert snap["holdings"] == [{"key": "005930:KR", "quantity": 10.0}]
        assert snap["stockEvaluation"] == 0.0
        assert snap["totalValue"] == snap["cashBalance"]

    def test_summary_lite_mode_skips_fx_fetch(self, trades_client):
        """withQuotes=false(신규 FE 기본)는 US 보유여도 fetch_usdkrw 미호출.

        lite 모드는 quotes={} 라 usdkrw 가 전혀 소비되지 않는다(FE 가 useFxRate 로 자체 환산) —
        임계 경로에서 불필요한 Yahoo 왕복(최대 2초) 제거 회귀 가드.
        """
        trade = _make_trade_row(
            asset_name="Apple", ticker_symbol="AAPL", country_code="US",
            exchange="NASDAQ", price=200.0, quantity=10.0, exchange_rate=1300.0,
        )
        account = _make_account_row()
        conn = FakeConnection([_to_record(trade)], [_to_record(account)])

        called = {"fx": False}

        async def must_not_call_fx(trades, state, client, *, force_refresh=False):
            called["fx"] = True
            return 1500.0

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.usdkrw_if_foreign", must_not_call_fx):
                resp = trades_client.get(
                    "/portfolio/summary", params={"withQuotes": "false"}
                )

        assert resp.status_code == 200
        assert called["fx"] is False, "lite 모드인데 환율 fetch 가 호출됨"

    def test_summary_other_country_skips_fx_fetch(self, trades_client):
        """country=OTHER(통화 KRW)만 보유 시 환율 네트워크 fetch 미호출 — 게이트는 통화 기준.

        with_quotes=true 라 usdkrw_if_foreign 자체는 호출되지만, 비-KRW 거래가 없어 내부 게이트가
        실제 fetch_usdkrw(Yahoo 왕복)를 건너뛴다 — fx 모듈의 fetch_usdkrw 를 spy 로 검증.
        """
        trade = _make_trade_row(
            asset_name="비트코인", ticker_symbol="BTC", country_code="OTHER",
        )
        account = _make_account_row()
        conn = FakeConnection([_to_record(trade)], [_to_record(account)])

        called = {"fx": False}

        async def must_not_call_fx(state, client, *, force_refresh=False):
            called["fx"] = True
            return 1500.0

        async def mock_quotes(state, keys, **kw):
            return {}

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", mock_quotes):
                with patch("invest_note_api.external.fx.fetch_usdkrw", must_not_call_fx):
                    resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        assert called["fx"] is False, "KRW 통화(OTHER)인데 환율 네트워크 fetch 가 호출됨"

    def test_summary_quote_failure_fallback(self, trades_client):
        """시세 fetch 실패 시에도 200 반환 (evaluation=null 허용)."""
        trade = _make_trade_row()
        account = _make_account_row()

        conn = FakeConnection(
            [_to_record(trade)],
            [_to_record(account)],
        )

        async def failing_quotes(state, keys, **kw):
            raise Exception("Naver down")

        with _patch_portfolio(conn):
            with patch("invest_note_api.routers.portfolio.fetch_quotes_by_keys", failing_quotes):
                resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        body = resp.json()
        # evaluation이 없어도 정상 응답
        assert body["positions"][0]["currentPrice"] is None

    def test_summary_401(self, auth_client):
        resp = auth_client.get("/portfolio/summary")
        assert resp.status_code == 401

    def test_summary_with_account_filter(self, trades_client):
        """accountId 쿼리 파라미터가 list_trades_with_account 에 전달되고 snapshots 가 좁혀지는지."""
        a1_id = "00000000-0000-0000-0000-000000000001"
        a2_id = "00000000-0000-0000-0000-000000000002"
        account_a1 = _make_account_row(id_=a1_id)
        account_a2 = _make_account_row(id_=a2_id)

        # capturing_list 가 list_trades_with_account 를 가로채므로 FakeConnection 의 trade response 는
        # 소비되지 않는다. accounts (list_accounts) 만 한 번 fetch → responses[0] = accounts.
        conn = FakeConnection(
            [_to_record(account_a1), _to_record(account_a2)],  # accounts (글로벌)
        )

        captured_kwargs: dict = {}

        async def capturing_list(conn_arg, user_id, **kwargs):
            captured_kwargs.update(kwargs)
            return []  # 빈 trades — totals/positions/snapshots 는 비어도 무방 (kwargs 만 검증)

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {}

        with _patch_portfolio(conn):
            with patch(
                "invest_note_api.routers.portfolio.list_trades_with_account",
                capturing_list,
            ):
                with patch(
                    "invest_note_api.routers.portfolio.fetch_quotes_by_keys",
                    mock_quotes,
                ):
                    resp = trades_client.get(
                        "/portfolio/summary", params={"accountId": a1_id}
                    )

        assert resp.status_code == 200
        assert captured_kwargs.get("account_id") == a1_id

        body = resp.json()
        # 글로벌 계좌가 2개라도 hasAccounts 는 true (정상)
        assert body["hasAccounts"] is True
        # snapshots 는 선택 계좌(a1)만 1개로 좁혀짐
        assert len(body["snapshots"]) == 1
        assert body["snapshots"][0]["account"]["id"] == a1_id

    def test_summary_without_account_filter_passes_none(self, trades_client):
        """accountId 미지정 시 list_trades_with_account 에 account_id=None 이 전달되고 모든 계좌의 snapshots 반환."""
        account_a1 = _make_account_row(id_="00000000-0000-0000-0000-000000000001")
        account_a2 = _make_account_row(id_="00000000-0000-0000-0000-000000000002")

        conn = FakeConnection(
            [_to_record(account_a1), _to_record(account_a2)],
        )

        captured_kwargs: dict = {}

        async def capturing_list(conn_arg, user_id, **kwargs):
            captured_kwargs.update(kwargs)
            return []

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {}

        with _patch_portfolio(conn):
            with patch(
                "invest_note_api.routers.portfolio.list_trades_with_account",
                capturing_list,
            ):
                with patch(
                    "invest_note_api.routers.portfolio.fetch_quotes_by_keys",
                    mock_quotes,
                ):
                    resp = trades_client.get("/portfolio/summary")

        assert resp.status_code == 200
        assert captured_kwargs.get("account_id") is None
        body = resp.json()
        assert len(body["snapshots"]) == 2  # 전체 계좌 모두

    def test_summary_refresh_param_forwards_force_refresh(self, trades_client):
        """refresh=1 (pull-to-refresh) → fetch_quotes_by_keys 에 force_refresh=True 전달.

        BE(`refresh`)↔FE(`refresh=1`) 계약을 잠근다 — 한쪽 이름이 바뀌면 freshness 가
        조용히 깨지므로(시세 캐시 우회 실패) 회귀로 잡는다.
        """
        account = _make_account_row(id_="00000000-0000-0000-0000-000000000001")
        captured: dict = {}

        async def mock_quotes(state, keys, *, client=None, force_refresh=False, **kw):
            captured["force_refresh"] = force_refresh
            return {}

        async def empty_list(conn_arg, user_id, **kwargs):
            return []

        for params, expected in (({"refresh": "1"}, True), ({}, False)):
            captured.clear()
            conn = FakeConnection([_to_record(account)])
            with _patch_portfolio(conn):
                with patch(
                    "invest_note_api.routers.portfolio.list_trades_with_account",
                    empty_list,
                ):
                    with patch(
                        "invest_note_api.routers.portfolio.fetch_quotes_by_keys",
                        mock_quotes,
                    ):
                        resp = trades_client.get("/portfolio/summary", params=params)
            assert resp.status_code == 200
            assert captured["force_refresh"] is expected

    def test_summary_with_nonexistent_account_filter(self, trades_client):
        """존재하지 않는 accountId 가 들어와도 has_accounts 는 글로벌 기준으로 true, has_trades 는 false."""
        account_a1 = _make_account_row(id_="00000000-0000-0000-0000-000000000001")

        conn = FakeConnection(
            [_to_record(account_a1)],  # accounts (글로벌)
        )

        async def capturing_list(conn_arg, user_id, **kwargs):
            return []  # 매칭 trade 없음

        async def mock_quotes(state, keys, *, client=None, **kw):
            return {}

        with _patch_portfolio(conn):
            with patch(
                "invest_note_api.routers.portfolio.list_trades_with_account",
                capturing_list,
            ):
                with patch(
                    "invest_note_api.routers.portfolio.fetch_quotes_by_keys",
                    mock_quotes,
                ):
                    resp = trades_client.get(
                        "/portfolio/summary",
                        params={"accountId": "00000000-0000-0000-0000-000000000099"},
                    )

        assert resp.status_code == 200
        body = resp.json()
        assert body["hasAccounts"] is True
        assert body["hasTrades"] is False
        assert body["snapshots"] == []
        assert body["positions"] == []

    def test_summary_rejects_malformed_account_id(self, trades_client):
        """비-UUID accountId 는 FastAPI 단에서 422 로 차단된다 (SQL 까지 도달 X)."""
        resp = trades_client.get(
            "/portfolio/summary", params={"accountId": "not-a-uuid"}
        )
        assert resp.status_code == 422
