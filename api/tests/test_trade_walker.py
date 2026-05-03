"""순수 함수 단위 테스트 — domain/trade_walker.py"""
from datetime import datetime, timezone


from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.trade_walker import (
    recomputed_avg_cost_deduction,
    stored_avg_cost_deduction,
    walk_trades,
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


def _accept_all(_t: Trade) -> bool:
    return True


def _by_traded_at(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: t.traded_at)


class TestBuyAccumulation:
    def test_running_state_accumulates_per_buy(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="b2", price=80000, quantity=5, traded_at=_dt("2024-01-02T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        assert [e.kind for e in events] == ["BUY", "BUY"]
        assert events[0].state_after.running_qty == 10
        assert events[0].state_after.running_cost == 700_000
        assert events[1].state_after.running_qty == 15
        assert events[1].state_after.running_cost == 1_100_000


class TestFifoConsumption:
    def test_sell_consumes_lots_in_order(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="b2", price=80000, quantity=10, traded_at=_dt("2024-01-02T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=90000, quantity=15, traded_at=_dt("2024-01-03T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        sell = events[-1]
        assert sell.kind == "SELL"
        assert sell.matched_qty == 15
        # FIFO: 첫 lot 10 전부 + 두번째 lot 5
        consumed_ids = [c.lot.source_trade.id for c in sell.consumed]
        consumed_qtys = [c.qty for c in sell.consumed]
        assert consumed_ids == ["b1", "b2"]
        assert consumed_qtys == [10, 5]

    def test_partial_sell_keeps_remainder_in_queue(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=4, traded_at=_dt("2024-01-02T09:00:00+09:00")),
            make_trade(id="s2", trade_type="SELL", price=90000, quantity=4, traded_at=_dt("2024-01-03T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        s1 = events[1]
        s2 = events[2]
        assert s2.consumed[0].lot.source_trade.id == "b1"
        assert s2.consumed[0].qty == 4
        assert s1.state_after.running_qty == 6
        assert s2.state_after.running_qty == 2


class TestOversellFlags:
    def test_oversell_flag_when_sell_exceeds_holding(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=15, traded_at=_dt("2024-01-02T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        sell = events[-1]
        assert sell.oversell is True
        assert sell.no_holding is False
        assert sell.matched_qty == 10
        assert sell.state_after.running_qty == 0

    def test_no_holding_flag_when_sell_with_zero_holding(self):
        trades = [
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=5, traded_at=_dt("2024-01-01T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        sell = events[0]
        assert sell.no_holding is True
        assert sell.oversell is True
        assert sell.matched_qty == 0
        assert sell.consumed == ()


class TestTrackFifoLotsFlag:
    def test_disabled_yields_empty_consumed(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=5, traded_at=_dt("2024-01-02T09:00:00+09:00")),
        ]
        events = list(walk_trades(
            trades, group_filter=_accept_all, sort_fn=_by_traded_at, track_fifo_lots=False,
        ))
        sell = events[-1]
        assert sell.consumed == ()
        # 그 외 상태는 동일하게 추적
        assert sell.matched_qty == 5
        assert sell.state_after.running_qty == 5


class TestCostDeductionPolicies:
    def test_recomputed_uses_running_wac(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="b2", price=80000, quantity=10, traded_at=_dt("2024-01-02T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=90000, quantity=5, traded_at=_dt("2024-01-03T09:00:00+09:00")),
        ]
        events = list(walk_trades(
            trades, group_filter=_accept_all, sort_fn=_by_traded_at,
            cost_deduction=recomputed_avg_cost_deduction,
        ))
        sell = events[-1]
        # avg = (700_000 + 800_000) / 20 = 75_000 → 차감 75_000 * 5 = 375_000
        assert sell.state_before.avg_cost == 75_000
        assert sell.state_after.running_cost == 1_500_000 - 375_000

    def test_stored_uses_trade_avg_buy_price(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(
                id="s1", trade_type="SELL", price=80000, quantity=4,
                avg_buy_price=72000.0,  # 저장값 사용
                traded_at=_dt("2024-01-02T09:00:00+09:00"),
            ),
        ]
        events = list(walk_trades(
            trades, group_filter=_accept_all, sort_fn=_by_traded_at,
            cost_deduction=stored_avg_cost_deduction,
        ))
        sell = events[-1]
        # 차감 72_000 * 4 = 288_000 (running_cost 700_000 - 288_000 = 412_000)
        assert sell.state_after.running_cost == 412_000

    def test_stored_handles_missing_avg_buy_price(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(
                id="s1", trade_type="SELL", price=80000, quantity=4,
                avg_buy_price=None,
                traded_at=_dt("2024-01-02T09:00:00+09:00"),
            ),
        ]
        events = list(walk_trades(
            trades, group_filter=_accept_all, sort_fn=_by_traded_at,
            cost_deduction=stored_avg_cost_deduction,
        ))
        # avg_buy_price=None → 0.0 차감 → running_cost 변동 없음
        assert events[-1].state_after.running_cost == 700_000


class TestGroupFilter:
    def test_only_filtered_trades_walked(self):
        trades = [
            make_trade(id="b1", ticker_symbol="005930", price=70000, quantity=10),
            make_trade(id="b2", ticker_symbol="000660", price=100000, quantity=5),
        ]
        events = list(walk_trades(
            trades,
            group_filter=lambda t: t.ticker_symbol == "005930",
            sort_fn=_by_traded_at,
        ))
        assert len(events) == 1
        assert events[0].trade.id == "b1"


class TestSortFnInjection:
    def test_buy_first_at_same_time(self):
        same_time = _dt("2024-01-01T09:00:00+09:00")
        trades = [
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=5, traded_at=same_time),
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=10, traded_at=same_time),
        ]
        # BUY 우선 정렬을 주입하면 BUY가 먼저
        def buy_first(ts: list[Trade]) -> list[Trade]:
            return sorted(ts, key=lambda t: (t.traded_at, 0 if t.trade_type == "BUY" else 1))
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=buy_first))
        assert [e.trade.id for e in events] == ["b1", "s1"]
        # SELL 시점에 보유가 충분 → no_holding=False
        assert events[1].no_holding is False


class TestRunningCostClamp:
    def test_negative_running_cost_clamped_to_zero(self):
        # stored_avg_cost_deduction에서 매우 큰 avg_buy_price를 강제해 음수 발생 시 clamp 검증
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(
                id="s1", trade_type="SELL", price=80000, quantity=5,
                avg_buy_price=1_000_000.0,  # 비현실적으로 큰 저장값
                traded_at=_dt("2024-01-02T09:00:00+09:00"),
            ),
        ]
        events = list(walk_trades(
            trades, group_filter=_accept_all, sort_fn=_by_traded_at,
            cost_deduction=stored_avg_cost_deduction,
        ))
        # 차감 5_000_000 > 700_000 → clamp 0
        assert events[-1].state_after.running_cost == 0.0

    def test_negative_running_qty_clamped_on_oversell(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=20, traded_at=_dt("2024-01-02T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        assert events[-1].state_after.running_qty == 0.0


class TestEarlyExitWithBreak:
    def test_caller_can_break_walker(self):
        trades = [
            make_trade(id="b1", price=70000, quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=15, traded_at=_dt("2024-01-02T09:00:00+09:00")),
            make_trade(id="b3", price=90000, quantity=20, traded_at=_dt("2024-01-03T09:00:00+09:00")),
        ]
        seen = []
        for ev in walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at, track_fifo_lots=False):
            seen.append(ev.trade.id)
            if ev.kind == "SELL" and ev.oversell:
                break
        assert seen == ["b1", "s1"]


class TestLotMetaPropagation:
    def test_consumed_lot_carries_buy_meta(self):
        trades = [
            make_trade(
                id="b1", price=70000, quantity=10,
                strategy_type="SWING",
                reasoning_tags=["TECHNICAL"],
                emotion="CONFIDENT",
                traded_at=_dt("2024-01-01T09:00:00+09:00"),
            ),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=5, traded_at=_dt("2024-01-02T09:00:00+09:00")),
        ]
        events = list(walk_trades(trades, group_filter=_accept_all, sort_fn=_by_traded_at))
        consumed = events[-1].consumed
        assert len(consumed) == 1
        assert consumed[0].lot.strategy == "SWING"
        assert consumed[0].lot.reasoning_tags == ("TECHNICAL",)
        assert consumed[0].lot.emotion == "CONFIDENT"
        assert consumed[0].lot.order == 0
