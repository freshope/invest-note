"""순수 함수 단위 테스트 — domain/realized_pnl.py"""
from datetime import datetime, timezone

import pytest

from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    sort_for_calc,
    compute_group_pnl,
    validate_mutation,
    build_pnl_map,
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


class TestSortForCalc:
    def test_buy_before_sell_same_time(self):
        buy = make_trade(id="b1", trade_type="BUY", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        result = sort_for_calc([sell, buy])
        assert result[0].id == "b1"
        assert result[1].id == "s1"

    def test_chronological_order(self):
        t1 = make_trade(id="t1", traded_at=_dt("2024-01-01T09:00:00+09:00"))
        t2 = make_trade(id="t2", traded_at=_dt("2024-01-02T09:00:00+09:00"))
        result = sort_for_calc([t2, t1])
        assert result[0].id == "t1"


class TestComputeGroupPnL:
    def _key(self) -> TradeGroupKey:
        return TradeGroupKey(ticker="005930", asset_name="삼성전자", country="KR", account_id="a1")

    def test_simple_buy_sell(self):
        trades = [
            make_trade(
                id="b1",
                trade_type="BUY",
                price=70000,
                quantity=10,
                strategy_type="LONG_TERM",
                traded_at=_dt("2024-01-01T09:00:00+09:00"),
            ),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert pytest.approx(result["s1"].profit_loss) == 100000.0
        assert pytest.approx(result["s1"].avg_buy_price) == 70000.0
        assert result["s1"].holding_days == 31
        assert result["s1"].strategy_type == "LONG_TERM"
        assert result["s1"].result == "SUCCESS"

    def test_result_derives_from_pnl_sign(self):
        # 손실 SELL → FAIL, 본전 SELL → BREAKEVEN.
        trades = [
            make_trade(id="b1", trade_type="BUY", price=80000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=70000, quantity=5, traded_at=_dt("2024-02-01T09:00:00+09:00")),
            make_trade(id="s2", trade_type="SELL", price=80000, quantity=5, traded_at=_dt("2024-03-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert result["s1"].result == "FAIL"
        assert result["s2"].result == "BREAKEVEN"

    def test_partial_sell(self):
        trades = [
            make_trade(id="b1", trade_type="BUY", price=60000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=70000, quantity=5, traded_at=_dt("2024-02-01T09:00:00+09:00")),
            make_trade(id="s2", trade_type="SELL", price=80000, quantity=5, traded_at=_dt("2024-03-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert pytest.approx(result["s1"].profit_loss) == 50000.0
        assert pytest.approx(result["s2"].profit_loss) == 100000.0
        assert result["s1"].holding_days == 31
        assert result["s2"].holding_days == 60

    def test_strategy_type_uses_largest_consumed_buy_lot(self):
        trades = [
            make_trade(
                id="b1",
                trade_type="BUY",
                price=60000,
                quantity=4,
                strategy_type="SCALPING",
                traded_at=_dt("2024-01-01T09:00:00+09:00"),
            ),
            make_trade(
                id="b2",
                trade_type="BUY",
                price=80000,
                quantity=6,
                strategy_type="SWING",
                traded_at=_dt("2024-01-02T09:00:00+09:00"),
            ),
            make_trade(id="s1", trade_type="SELL", price=90000, quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert result["s1"].strategy_type == "SWING"

    def test_reasoning_tags_emotion_from_latest_consumed_buy(self):
        # 두 BUY를 모두 소비하면 가장 최근(b2) BUY의 tags/custom_tags/emotion이 SELL에 적용된다.
        trades = [
            make_trade(
                id="b1",
                trade_type="BUY",
                quantity=5,
                reasoning_tags=["FUNDAMENTAL"],
                custom_tags=["배당"],
                emotion="CALM",
                traded_at=_dt("2024-01-01T09:00:00+09:00"),
            ),
            make_trade(
                id="b2",
                trade_type="BUY",
                quantity=5,
                reasoning_tags=["TECHNICAL", "NEWS"],
                custom_tags=["테마주", "단타"],
                emotion="CONFIDENT",
                traded_at=_dt("2024-01-05T09:00:00+09:00"),
            ),
            make_trade(
                id="s1",
                trade_type="SELL",
                quantity=10,
                traded_at=_dt("2024-02-01T09:00:00+09:00"),
            ),
        ]
        result = compute_group_pnl(trades, self._key())
        assert result["s1"].reasoning_tags == ["TECHNICAL", "NEWS"]
        assert result["s1"].custom_tags == ["테마주", "단타"]
        assert result["s1"].emotion == "CONFIDENT"

    def test_partial_sell_uses_only_consumed_buy(self):
        # 첫 SELL은 b1만 소비 → b1의 tags/emotion. 두 번째 SELL은 b2 소비 → b2의 값.
        trades = [
            make_trade(
                id="b1",
                trade_type="BUY",
                quantity=5,
                reasoning_tags=["FUNDAMENTAL"],
                emotion="CALM",
                traded_at=_dt("2024-01-01T09:00:00+09:00"),
            ),
            make_trade(
                id="b2",
                trade_type="BUY",
                quantity=5,
                reasoning_tags=["TECHNICAL"],
                emotion="FOMO",
                traded_at=_dt("2024-01-05T09:00:00+09:00"),
            ),
            make_trade(id="s1", trade_type="SELL", quantity=5, traded_at=_dt("2024-02-01T09:00:00+09:00")),
            make_trade(id="s2", trade_type="SELL", quantity=5, traded_at=_dt("2024-03-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert result["s1"].reasoning_tags == ["FUNDAMENTAL"]
        assert result["s1"].emotion == "CALM"
        assert result["s2"].reasoning_tags == ["TECHNICAL"]
        assert result["s2"].emotion == "FOMO"

    def test_no_consumed_buy_returns_empty_meta(self):
        # oversell: 소비 BUY 없으면 빈 tags / None emotion.
        trades = [
            make_trade(id="s1", trade_type="SELL", quantity=5, traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        # SELL 단독 호출은 oversell 검증을 거치지 않은 상태의 그룹 계산 동작 검증
        result = compute_group_pnl(trades, self._key())
        assert result["s1"].reasoning_tags == []
        assert result["s1"].emotion is None

    def test_commission_and_tax_deducted(self):
        trades = [
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=10, commission=500, tax=200,
                       traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert pytest.approx(result["s1"].profit_loss) == 100000.0 - 500 - 200

    def test_no_sell_returns_empty(self):
        trades = [make_trade(id="b1", trade_type="BUY", price=70000, quantity=10)]
        result = compute_group_pnl(trades, self._key())
        assert result == {}

    def test_oversell_clamps_cost(self):
        """매도 수량 > 매수 수량: runningCost가 음수로 내려가지 않음."""
        trades = [
            make_trade(id="b1", trade_type="BUY", price=50000, quantity=5, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=60000, quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        result = compute_group_pnl(trades, self._key())
        assert "s1" in result
        assert result["s1"].running_qty_after == 0.0


class TestValidateMutation:
    def test_insert_buy_ok(self):
        trade = make_trade(id="b1", trade_type="BUY", quantity=10)
        ok, msg, _ = validate_mutation([], "insert", trade)
        assert ok

    def test_insert_sell_no_holding(self):
        sell = make_trade(id="s1", trade_type="SELL", quantity=5)
        ok, msg, _ = validate_mutation([], "insert", sell)
        assert not ok
        assert "보유 수량이 없어" in msg

    def test_insert_sell_oversell(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=5, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        ok, msg, _ = validate_mutation([buy], "insert", sell)
        assert not ok
        assert "부족한 매도" in msg

    def test_insert_sell_exact_ok(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        ok, msg, ids = validate_mutation([buy], "insert", sell)
        assert ok
        assert "s1" in ids

    def test_delete_trade_ok(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        # deleting buy would leave sell with no holding
        ok, msg, _ = validate_mutation([buy, sell], "delete", buy)
        assert not ok

    def test_update_sell_ok(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, price=80000, traded_at=_dt("2024-02-01T09:00:00+09:00"))
        ok, msg, ids = validate_mutation([buy, sell], "update", sell, {"price": 85000})
        assert ok


class TestBuildPnlMap:
    def test_only_sells_included(self):
        buy = make_trade(id="b1", trade_type="BUY", profit_loss=None)
        sell = make_trade(id="s1", trade_type="SELL", profit_loss=50000.0)
        result = build_pnl_map([buy, sell])
        assert "b1" not in result
        assert result["s1"] == 50000.0

    def test_null_profit_loss_defaults_to_zero(self):
        sell = make_trade(id="s1", trade_type="SELL", profit_loss=None)
        result = build_pnl_map([sell])
        assert result["s1"] == 0.0
