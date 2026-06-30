"""analysis 라우터 통합 테스트 — FakePool 기반."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import pytest

from invest_note_api.config import Settings, get_settings
from invest_note_api.domain.trade_utils import KST
from tests.conftest import TEST_USER_ID, dt as _dt
from tests.fake_pool import FakeConnection, make_fake_acquire


def _make_trade_row(
    id_="t1",
    trade_type="BUY",
    ticker="005930",
    asset_name="삼성전자",
    price=70000.0,
    quantity=10.0,
    traded_at=None,
    profit_loss=None,
    avg_buy_price=None,
    holding_days=None,
    strategy_type=None,
    emotion=None,
    result=None,
    reasoning_tags=None,
    country_code="KR",
    total_amount=None,
    buy_reason=None,
    exchange_rate=1.0,
    custom_tags=None,
) -> dict:
    now = _dt("2026-04-20T09:00:00+09:00")
    return {
        "id": id_,
        "user_id": TEST_USER_ID,
        "account_id": "a1",
        "asset_name": asset_name,
        "ticker_symbol": ticker,
        "market_type": "STOCK",
        "trade_type": trade_type,
        "price": price,
        "quantity": quantity,
        "total_amount": total_amount if total_amount is not None else price * quantity,
        "traded_at": traded_at or now,
        "strategy_type": strategy_type,
        "reasoning_tags": reasoning_tags or [],
        "custom_tags": custom_tags or [],
        "buy_reason": buy_reason,
        "sell_reason": None,
        "emotion": emotion,
        "result": result,
        "profit_loss": profit_loss,
        "avg_buy_price": avg_buy_price,
        "holding_days": holding_days,
        "country_code": country_code,
        "exchange": "",
        "exchange_rate": exchange_rate,
        "commission": 0.0,
        "tax": 0.0,
        "created_at": _dt("2024-01-01T00:00:00Z"),
        "updated_at": _dt("2024-01-01T00:00:00Z"),
    }


def _patched_get(client, path: str):
    """라우터 패치 + 빈 quotes 응답 적용 후 GET."""
    with patch(
        "invest_note_api.routers.analysis.fetch_quotes_by_keys",
        new=AsyncMock(return_value={}),
    ):
        return client.get(path)


class TestAnalysisDashboard:
    def test_dashboard_forwards_env_providers(self, trades_client):
        """QUOTE_PROVIDERS env 가 fetch_quotes_by_keys providers 로 전달 — 죽은 설정 가드."""
        conn = FakeConnection([])
        received: dict = {}

        async def mock_quotes(state, keys, *, client=None, force_refresh=False, providers=None, **kw):
            received["providers"] = providers
            return {}

        trades_client.app.dependency_overrides[get_settings] = lambda: Settings(
            supabase_url="https://test.supabase.co", quote_providers="yahoo"
        )
        try:
            with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
                with patch("invest_note_api.routers.analysis.fetch_quotes_by_keys", mock_quotes):
                    resp = trades_client.get("/v1/analysis/dashboard")
        finally:
            trades_client.app.dependency_overrides.pop(get_settings, None)

        assert resp.status_code == 200
        assert received["providers"] == ["yahoo"]

    # --- summary 영역 ---

    def test_empty_trades(self, trades_client):
        conn = FakeConnection([])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "all"
        summary = data["summary"]
        assert summary["totalTrades"] == 0
        assert summary["sellTrades"] == 0
        assert summary["winRate"] == 0.0
        assert summary["byStrategy"] == []
        behavior = data["behavior"]
        assert behavior["concentration"]["hhi"] == 0.0
        assert isinstance(data["suggestions"]["suggestions"], list)

    def test_buy_and_sell(self, trades_client):
        buy = _make_trade_row(id_="b1", trade_type="BUY", price=70000.0, quantity=10.0, strategy_type="SWING")
        sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            price=75000.0,
            quantity=10.0,
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            profit_loss=50000.0,
            avg_buy_price=70000.0,
            holding_days=2,
            strategy_type="SWING",
            result="SUCCESS",
        )
        conn = FakeConnection([buy, sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert summary["totalTrades"] == 2
        assert summary["sellTrades"] == 1
        assert summary["winRate"] == 100.0
        assert summary["totalProfitLoss"] == pytest.approx(50000.0, rel=1e-6)
        assert len(summary["byStrategy"]) == 1
        assert summary["byStrategy"][0]["type"] == "SWING"
        assert summary["strategyAdherenceRate"] == 100.0
        assert summary["byStrategyAdherence"][0]["type"] == "FOLLOWED"
        # PnL 약어 키는 대문자 'L' (FE 타입 호환)
        assert "sumPnL" in summary["byStrategy"][0]
        assert "sumPnL" in summary["byStrategyAdherence"][0]

    def test_by_custom_tag_aggregation(self, trades_client):
        """SELL의 custom_tags가 byCustomTag 버킷별 거래수/승률/손익으로 집계되고
        응답 키가 camelCase(byCustomTag, winRate, sumPnL)인지 확인."""
        buy = _make_trade_row(id_="b1", trade_type="BUY", price=70000.0, quantity=10.0)
        sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            price=75000.0,
            quantity=10.0,
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            profit_loss=50000.0,
            avg_buy_price=70000.0,
            holding_days=2,
            result="SUCCESS",
            custom_tags=["배당", "테마주"],  # 매수에서 자동 상속된 상태를 시뮬레이션
        )
        conn = FakeConnection([buy, sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        by_custom = {c["tag"]: c for c in summary["byCustomTag"]}
        assert set(by_custom) == {"배당", "테마주"}
        for tag in ("배당", "테마주"):
            assert by_custom[tag]["count"] == 1
            assert by_custom[tag]["winRate"] == 100.0
            assert by_custom[tag]["sumPnL"] == pytest.approx(50000.0, rel=1e-6)

    def test_by_custom_tag_empty_when_none(self, trades_client):
        """custom_tags 미입력이면 byCustomTag는 빈 배열(UNTAGGED 버킷 없음)."""
        buy = _make_trade_row(id_="b1", trade_type="BUY", price=70000.0, quantity=10.0)
        sell = _make_trade_row(
            id_="s1", trade_type="SELL", price=75000.0, quantity=10.0,
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            profit_loss=50000.0, avg_buy_price=70000.0, holding_days=2, result="SUCCESS",
        )
        conn = FakeConnection([buy, sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        assert resp.json()["summary"]["byCustomTag"] == []

    def test_us_realized_pnl_is_stored_krw(self, trades_client):
        """US SELL 실현손익은 저장값이 이미 KRW(거래시점 환율로 compute_group_pnl 이 고정).

        analysis 는 저장 profit_loss(KRW)를 환산 없이 그대로 합산한다(현재 환율 무관).
        """
        buy = _make_trade_row(
            id_="b1", trade_type="BUY", ticker="AAPL", asset_name="Apple",
            price=200.0, quantity=10.0, country_code="US", exchange_rate=1500.0,
        )
        sell = _make_trade_row(
            id_="s1", trade_type="SELL", ticker="AAPL", asset_name="Apple",
            price=210.0, quantity=10.0, country_code="US", exchange_rate=1520.0,
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            # 저장 profit_loss = KRW: 210×10×1520 - 200×10×1500 = 192,000
            profit_loss=192000.0, avg_buy_price=300000.0, holding_days=2,
        )
        conn = FakeConnection([buy, sell])

        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            with patch("invest_note_api.routers.analysis.fetch_quotes_by_keys", new=AsyncMock(return_value={})):
                # US 거래 존재 → 라우터가 usdkrw_if_foreign 으로 환율을 받으므로 실 네트워크를 차단한다.
                with patch("invest_note_api.routers.analysis.usdkrw_if_foreign", new=AsyncMock(return_value=1490.0)):
                    resp = trades_client.get("/v1/analysis/dashboard")

        assert resp.status_code == 200
        summary = resp.json()["summary"]
        # 저장 KRW(192,000)를 그대로 합산
        assert summary["totalProfitLoss"] == pytest.approx(192000.0, rel=1e-6)
        # result_input_rate 는 제거됨 (자동 유도값이라 의미 없음)
        assert "resultInputRate" not in summary

    def test_fx_missing_is_separated_from_missing_quote(self, trades_client):
        """US 보유 + 시세 있음 + 현재 환율 None → evaluation None.

        시세는 받았으므로 missingQuoteTickers(시세 미조회)엔 넣지 않고 fxMissing(환율 미상)으로
        노출한다 — 홈(portfolio.applyQuotesToTotals)과 동일 의미. '시세 미조회' 오라벨 방지.
        """
        buy = _make_trade_row(
            id_="b1", trade_type="BUY", ticker="AAPL", asset_name="Apple",
            price=200.0, quantity=10.0, country_code="US", exchange_rate=1300.0,
        )
        conn = FakeConnection([buy])

        async def quote_with_price(state, keys, **kw):
            return {"AAPL:US": {"price": 220.0, "currency": "USD", "as_of": ""}}

        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            with patch("invest_note_api.routers.analysis.fetch_quotes_by_keys", quote_with_price):
                # 현재 환율 미수신(None) → US 평가액 KRW 미상.
                with patch("invest_note_api.routers.analysis.usdkrw_if_foreign", new=AsyncMock(return_value=None)):
                    resp = trades_client.get("/v1/analysis/dashboard")

        assert resp.status_code == 200
        body = resp.json()
        # 시세는 있으므로 '시세 미조회'가 아니라 '환율 미상'으로 분류.
        assert "Apple" not in body["missingQuoteTickers"]
        assert body["fxMissing"] is True

    def test_no_quote_still_in_missing_quote_tickers(self, trades_client):
        """시세 자체가 없는(quote fetch 빈 결과) 종목은 여전히 missingQuoteTickers 에 노출."""
        buy = _make_trade_row(
            id_="b1", trade_type="BUY", ticker="005930", asset_name="삼성전자",
            price=70000.0, quantity=10.0, country_code="KR",
        )
        conn = FakeConnection([buy])

        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            with patch("invest_note_api.routers.analysis.fetch_quotes_by_keys", new=AsyncMock(return_value={})):
                resp = trades_client.get("/v1/analysis/dashboard")

        assert resp.status_code == 200
        body = resp.json()
        assert "삼성전자" in body["missingQuoteTickers"]
        assert body["fxMissing"] is False

    def test_input_rates_shape(self, trades_client):
        # BUY 2건: 1건은 buy_reason 채움, 1건은 None → buyReason = 50.0
        buy_with = _make_trade_row(
            id_="b1", trade_type="BUY", buy_reason="기술적 분석"
        )
        buy_without = _make_trade_row(
            id_="b2", trade_type="BUY", buy_reason=None,
            traded_at=_dt("2026-04-20T10:00:00+09:00"),
        )
        conn = FakeConnection([buy_with, buy_without])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        input_rates = resp.json()["behavior"]["inputRates"]
        # 신규 buyReason 필드 존재 + 기존 result 필드 제거 확인
        assert input_rates["buyReason"] == 50.0
        assert "result" not in input_rates

    def test_period_filter(self, trades_client):
        # recent_sell은 실행 시각 기준 5일 전 — 시간이 흘러도 1m 안에 유지
        recent_ts = datetime.now(KST) - timedelta(days=5)
        old_buy = _make_trade_row(id_="b1", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        recent_sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            traded_at=recent_ts,
            result="SUCCESS",
        )
        conn = FakeConnection([old_buy, recent_sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard?period=1m")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "1m"
        # old_buy(2024)는 1m 필터로 제외, 매도만 남음
        assert data["summary"]["totalTrades"] == 1

    # --- behavior 영역 ---

    def test_quote_failure_fallback(self, trades_client):
        buy = _make_trade_row(id_="b1", price=70000.0, quantity=5.0)
        conn = FakeConnection([buy])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            with patch(
                "invest_note_api.routers.analysis.fetch_quotes_by_keys",
                new=AsyncMock(side_effect=Exception("timeout")),
            ):
                resp = trades_client.get("/v1/analysis/dashboard")
        assert resp.status_code == 200
        assert "profile" in resp.json()["behavior"]

    def test_holding_period_dist(self, trades_client):
        buy = _make_trade_row(id_="b1", traded_at=_dt("2026-04-10T09:00:00+09:00"))
        sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            holding_days=12,
        )
        conn = FakeConnection([buy, sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard?period=all")
        assert resp.status_code == 200
        behavior = resp.json()["behavior"]
        assert len(behavior["holdingPeriodDist"]) >= 1
        dist_buckets = [d["bucket"] for d in behavior["holdingPeriodDist"]]
        assert "1개월 이내" in dist_buckets or "1주 이내" in dist_buckets

    def test_position_size_dist(self, trades_client):
        buy = _make_trade_row(id_="b1", price=80000.0, quantity=5.0, total_amount=400000.0)
        conn = FakeConnection([buy])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard?period=all")
        assert resp.status_code == 200
        behavior = resp.json()["behavior"]
        assert len(behavior["positionSizeDist"]) == 1
        assert behavior["positionSizeDist"][0]["bucket"] == "50만 미만"

    def test_position_size_dist_us_bucketed_in_krw(self, trades_client):
        # $200 × 10 = native total_amount 2,000(USD). 거래 시점 환율 1500 → KRW 원금
        # 3,000,000 → "100~500만" 버킷(native 2,000 으로 잘못 버킷팅하면 "50만 미만").
        buy = _make_trade_row(
            id_="b1",
            price=200.0,
            quantity=10.0,
            total_amount=2000.0,
            country_code="US",
            exchange_rate=1500.0,
        )
        conn = FakeConnection([buy])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            with patch("invest_note_api.routers.analysis.usdkrw_if_foreign", new=AsyncMock(return_value=1490.0)):
                resp = _patched_get(trades_client, "/v1/analysis/dashboard?period=all")
        assert resp.status_code == 200
        behavior = resp.json()["behavior"]
        assert len(behavior["positionSizeDist"]) == 1
        # 현재 환율(1490)이 아닌 거래 시점 환율(1500)로 환산되어야 함.
        assert behavior["positionSizeDist"][0]["bucket"] == "100~500만"

    # --- suggestions 영역 ---

    def test_suggestions_schema(self, trades_client):
        conn = FakeConnection([])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        suggestions_block = resp.json()["suggestions"]
        assert "period" in suggestions_block
        assert "suggestions" in suggestions_block

    def test_losing_strategy_appears(self, trades_client):
        trades = [
            _make_trade_row(id_=f"b{i}", trade_type="BUY", strategy_type="SCALPING")
            for i in range(6)
        ] + [
            _make_trade_row(
                id_=f"s{i}",
                trade_type="SELL",
                strategy_type="SCALPING",
                result="FAIL",
            )
            for i in range(6)
        ]
        conn = FakeConnection(trades)
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()["suggestions"]["suggestions"]]
        assert "losing_strategy" in ids

    def test_severity_order(self, trades_client):
        trades = [
            _make_trade_row(id_=f"b{i}", trade_type="BUY", strategy_type="SCALPING")
            for i in range(6)
        ] + [
            _make_trade_row(
                id_=f"s{i}",
                trade_type="SELL",
                strategy_type="SCALPING",
                result="FAIL",
                emotion="FOMO",
            )
            for i in range(6)
        ]
        conn = FakeConnection(trades)
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]["suggestions"]
        severity_order = {"critical": 0, "warn": 1, "info": 2}
        for a, b in zip(suggestions, suggestions[1:]):
            assert severity_order[a["severity"]] <= severity_order[b["severity"]]

    # --- 인증 / SQL 호출 횟수 ---

    def test_401_without_token(self, auth_client):
        resp = auth_client.get("/v1/analysis/dashboard")
        assert resp.status_code == 401

    def test_list_trades_called_once(self, trades_client):
        """단일 dashboard 요청에서 trades 조회 SQL이 1회만 발행됨."""
        buy = _make_trade_row(id_="b1", trade_type="BUY", strategy_type="SWING")
        sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            profit_loss=10000.0,
            avg_buy_price=70000.0,
            holding_days=1,
            strategy_type="SWING",
            result="SUCCESS",
        )
        conn = FakeConnection([buy, sell])
        fetch_queries: list[str] = []
        original_fetch = conn.fetch

        async def counting_fetch(query: str, *args):
            fetch_queries.append(query)
            return await original_fetch(query, *args)

        conn.fetch = counting_fetch  # type: ignore[assignment]

        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/v1/analysis/dashboard")
        assert resp.status_code == 200
        trade_queries = [q for q in fetch_queries if "FROM TRADES" in q.upper()]
        assert len(trade_queries) == 1, fetch_queries
