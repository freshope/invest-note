"""순수 함수 단위 테스트 — domain/holdings.py"""
from datetime import datetime, timezone


from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.realized_pnl import TradeGroupKey
from invest_note_api.domain.holdings import (
    compute_holding_summary,
    compute_flexible_breakdown,
)


def _key(ticker: str | None = "005930", asset_name: str = "삼성전자", country: str = "KR", account_id: str = "a1") -> TradeGroupKey:
    return TradeGroupKey(ticker=ticker, asset_name=asset_name, country=country, account_id=account_id)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def make_trade(**kwargs) -> Trade:
    defaults = dict(
        id="t1",
        user_id="u1",
        account_id="a1",
        asset_name="삼성전자",
        ticker_symbol="005930",
        market_type="STOCK",
        trade_type="BUY",
        price=70000.0,
        quantity=10.0,
        total_amount=700000.0,
        traded_at=_dt("2024-01-10T09:00:00+09:00"),
        strategy_type=None,
        reasoning_tags=[],
        buy_reason=None,
        sell_reason=None,
        emotion=None,
        result=None,
        profit_loss=None,
        avg_buy_price=None,
        holding_days=None,
        country_code="KR",
        exchange="",
        commission=0.0,
        tax=0.0,
        created_at=_dt("2024-01-01T00:00:00Z"),
        updated_at=_dt("2024-01-01T00:00:00Z"),
    )
    defaults.update(kwargs)
    return Trade(**defaults)


class TestComputeHoldingSummary:
    def test_simple_holding(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10)
        result = compute_holding_summary([buy], _key())
        assert result.quantity == 10.0
        assert result.avg_buy_price == 70000.0

    def test_holding_after_partial_sell(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=3, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        result = compute_holding_summary([buy, sell], _key())
        assert result.quantity == 7.0
        assert result.avg_buy_price == 70000.0

    def test_weighted_average_after_multiple_buys_and_sell(self):
        b1 = make_trade(
            id="b1",
            trade_type="BUY",
            quantity=10,
            price=1000,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        b2 = make_trade(
            id="b2",
            trade_type="BUY",
            quantity=10,
            price=2000,
            traded_at=_dt("2024-01-02T09:00:00+09:00"),
        )
        sell = make_trade(id="s1", trade_type="SELL", quantity=5, traded_at=_dt("2024-01-03T09:00:00+09:00"))

        result = compute_holding_summary([b1, b2, sell], _key())

        assert result.quantity == 15.0
        assert result.avg_buy_price == 1500.0


class TestComputeFlexibleBreakdown:
    def test_breakdown_uses_stored_avg_buy_price(self):
        sell = make_trade(id="s1", trade_type="SELL", price=80000, quantity=10, avg_buy_price=70000.0, profit_loss=100000.0)
        bd = compute_flexible_breakdown(sell)
        assert bd.sell_price == 80000.0
        assert bd.avg_cost_price == 70000.0
        assert bd.pnl == 100000.0
        assert bd.sell_amount == 800000.0
        assert bd.cost_basis == 700000.0

    def test_null_avg_buy_price_defaults_zero(self):
        sell = make_trade(id="s1", trade_type="SELL", price=80000, quantity=10, avg_buy_price=None, profit_loss=None)
        bd = compute_flexible_breakdown(sell)
        assert bd.avg_cost_price == 0.0
        assert bd.pnl == 0.0


