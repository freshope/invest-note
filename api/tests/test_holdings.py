"""순수 함수 단위 테스트 — domain/holdings.py"""
from datetime import datetime, timezone


from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.holdings import (
    LotKey,
    compute_lot_quantity,
    compute_total_holding,
    compute_flexible_breakdown,
    compute_flexible_holding_days,
    find_latest_buy_strategy,
)


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


class TestComputeLotQuantity:
    def test_buy_increases_qty(self):
        key = LotKey(ticker="005930", country="KR", account_id="a1")
        buy = make_trade(id="b1", trade_type="BUY", quantity=10)
        assert compute_lot_quantity([buy], key) == 10.0

    def test_sell_decreases_qty(self):
        key = LotKey(ticker="005930", country="KR", account_id="a1")
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=4, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        assert compute_lot_quantity([buy, sell], key) == 6.0

    def test_different_account_excluded(self):
        key = LotKey(ticker="005930", country="KR", account_id="a1")
        other = make_trade(id="b2", trade_type="BUY", quantity=10, account_id="a2")
        assert compute_lot_quantity([other], key) == 0.0


class TestComputeTotalHolding:
    def test_simple_holding(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10)
        result = compute_total_holding([buy], ticker="005930", asset_name="삼성전자", country="KR", account_id="a1")
        assert result == 10.0

    def test_holding_after_partial_sell(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=3, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        result = compute_total_holding([buy, sell], ticker="005930", asset_name="삼성전자", country="KR", account_id="a1")
        assert result == 7.0

    def test_flexible_match_by_asset_name(self):
        """ticker 없이 asset_name으로도 매칭 가능."""
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, ticker_symbol="005930")
        result = compute_total_holding([buy], ticker=None, asset_name="삼성전자", country="KR", account_id="a1")
        assert result == 10.0


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


class TestComputeFlexibleHoldingDays:
    def test_simple_10_days(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-01-11T09:00:00+09:00"))
        days = compute_flexible_holding_days(sell, [buy, sell])
        assert days == 10

    def test_fifo_weighted_avg_15_days(self):
        b1 = make_trade(id="b1", trade_type="BUY", quantity=5, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        b2 = make_trade(id="b2", trade_type="BUY", quantity=5, traded_at=_dt("2024-01-11T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-01-21T09:00:00+09:00"))
        # b1: 20일 * 5주, b2: 10일 * 5주 → 가중평균 15일
        days = compute_flexible_holding_days(sell, [b1, b2, sell])
        assert days == 15

    def test_fifo_multi_lot_13_days(self):
        b1 = make_trade(id="b1", trade_type="BUY", quantity=3, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        b2 = make_trade(id="b2", trade_type="BUY", quantity=7, traded_at=_dt("2024-01-11T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-01-21T09:00:00+09:00"))
        # (3*20 + 7*10) / 10 = 13
        days = compute_flexible_holding_days(sell, [b1, b2, sell])
        assert days == 13

    def test_no_buy_returns_none(self):
        sell = make_trade(id="s1", trade_type="SELL", quantity=5)
        days = compute_flexible_holding_days(sell, [sell])
        assert days is None

    def test_sequential_sells_each_consumes_correct_lot(self):
        b1 = make_trade(id="b1", trade_type="BUY", quantity=5, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        b2 = make_trade(id="b2", trade_type="BUY", quantity=5, traded_at=_dt("2024-01-11T09:00:00+09:00"))
        s1 = make_trade(id="s1", trade_type="SELL", quantity=5, traded_at=_dt("2024-01-21T09:00:00+09:00"))
        s2 = make_trade(id="s2", trade_type="SELL", quantity=5, traded_at=_dt("2024-01-21T09:00:00+09:00"),
                        created_at=_dt("2024-01-02T00:00:00Z"))
        all_trades = [b1, b2, s1, s2]
        d1 = compute_flexible_holding_days(s1, all_trades)
        d2 = compute_flexible_holding_days(s2, all_trades)
        assert d1 == 20  # b1 소비
        assert d2 == 10  # b2 소비


class TestFindLatestBuyStrategy:
    def test_returns_most_recent_buy_strategy(self):
        b1 = make_trade(id="b1", trade_type="BUY", strategy_type="SWING", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        b2 = make_trade(id="b2", trade_type="BUY", strategy_type="LONG_TERM", traded_at=_dt("2024-02-01T09:00:00+09:00"))
        key = LotKey(ticker="005930", country="KR", account_id="a1")
        result = find_latest_buy_strategy([b1, b2], key)
        assert result == "LONG_TERM"

    def test_no_buy_returns_none(self):
        sell = make_trade(id="s1", trade_type="SELL")
        key = LotKey(ticker="005930", country="KR", account_id="a1")
        result = find_latest_buy_strategy([sell], key)
        assert result is None
