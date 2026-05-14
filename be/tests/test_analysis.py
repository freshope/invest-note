"""analysis 라우터 통합 테스트 — FakePool 기반."""
from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest

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
        "buy_reason": None,
        "sell_reason": None,
        "emotion": emotion,
        "result": result,
        "profit_loss": profit_loss,
        "avg_buy_price": avg_buy_price,
        "holding_days": holding_days,
        "country_code": country_code,
        "exchange": "",
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
    # --- summary 영역 ---

    def test_empty_trades(self, trades_client):
        conn = FakeConnection([])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
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
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
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

    def test_period_filter(self, trades_client):
        old_buy = _make_trade_row(id_="b1", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        recent_sell = _make_trade_row(
            id_="s1",
            trade_type="SELL",
            traded_at=_dt("2026-04-22T09:00:00+09:00"),
            result="SUCCESS",
        )
        conn = FakeConnection([old_buy, recent_sell])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/api/analysis/dashboard?period=1m")
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
                resp = trades_client.get("/api/analysis/dashboard")
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
            resp = _patched_get(trades_client, "/api/analysis/dashboard?period=all")
        assert resp.status_code == 200
        behavior = resp.json()["behavior"]
        assert len(behavior["holdingPeriodDist"]) >= 1
        dist_buckets = [d["bucket"] for d in behavior["holdingPeriodDist"]]
        assert "1개월 이내" in dist_buckets or "1주 이내" in dist_buckets

    def test_position_size_dist(self, trades_client):
        buy = _make_trade_row(id_="b1", price=80000.0, quantity=5.0, total_amount=400000.0)
        conn = FakeConnection([buy])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/api/analysis/dashboard?period=all")
        assert resp.status_code == 200
        behavior = resp.json()["behavior"]
        assert len(behavior["positionSizeDist"]) == 1
        assert behavior["positionSizeDist"][0]["bucket"] == "50만 미만"

    # --- suggestions 영역 ---

    def test_suggestions_schema(self, trades_client):
        conn = FakeConnection([])
        with patch("invest_note_api.routers.analysis.acquire_for_user", make_fake_acquire(conn)):
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
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
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
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
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]["suggestions"]
        severity_order = {"critical": 0, "warn": 1, "info": 2}
        for a, b in zip(suggestions, suggestions[1:]):
            assert severity_order[a["severity"]] <= severity_order[b["severity"]]

    # --- 인증 / SQL 호출 횟수 ---

    def test_401_without_token(self, auth_client):
        resp = auth_client.get("/api/analysis/dashboard")
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
            resp = _patched_get(trades_client, "/api/analysis/dashboard")
        assert resp.status_code == 200
        trade_queries = [q for q in fetch_queries if "FROM TRADES" in q.upper()]
        assert len(trade_queries) == 1, fetch_queries
