"""순수 함수 단위 테스트 — domain/portfolio.py"""
from datetime import datetime, timezone
from uuid import UUID

import pytest

from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.portfolio import (
    Account,
    Position,
    QuoteMap,
    build_positions,
    merge_quotes,
    build_account_snapshots,
    build_totals,
)
from invest_note_api.domain.realized_pnl import build_pnl_map


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


def make_account(**kwargs) -> Account:
    defaults = dict(
        id="a1",
        user_id="u1",
        name="테스트 계좌",
        broker=None,
        cash_balance=1000000.0,
        created_at=_dt("2024-01-01T00:00:00Z"),
        updated_at=_dt("2024-01-01T00:00:00Z"),
    )
    defaults.update(kwargs)
    return Account(**defaults)


class TestBuildPositions:
    def test_single_buy(self):
        buy = make_trade(id="b1", trade_type="BUY", price=70000, quantity=10)
        positions, _ = build_positions([buy])
        assert len(positions) == 1
        pos = positions[0]
        assert pos.ticker == "005930"
        assert pos.holding_quantity == 10.0
        assert pytest.approx(pos.avg_buy_price) == 70000.0

    def test_no_positions_after_full_sell(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", quantity=10, avg_buy_price=70000.0, profit_loss=0.0,
                          traded_at=_dt("2024-02-01T09:00:00+09:00"))
        positions, lot_map = build_positions([buy, sell])
        assert len(positions) == 0
        # lot 은 lot_map 에 남아있되 running_qty 가 0 — build_account_snapshots 가
        # `<= 0` 필터로 거른다는 invariant. 향후 refactor 가 zero-qty lot 을 제거하면 깨짐.
        assert len(lot_map) == 1
        assert next(iter(lot_map.values())).running_qty == 0.0

    def test_two_accounts_separate_lots(self):
        b1 = make_trade(id="b1", trade_type="BUY", quantity=5, account_id="a1")
        b2 = make_trade(id="b2", trade_type="BUY", quantity=3, account_id="a2")
        # Same ticker, different accounts → merged into one position
        positions, _ = build_positions([b1, b2])
        # Both lots positive → same display key "005930:KR" → merged
        assert len(positions) == 1
        assert positions[0].holding_quantity == 8.0

    def test_last_note_from_buy_reason(self):
        buy = make_trade(id="b1", trade_type="BUY", buy_reason="기술적 분석 신호")
        positions, _ = build_positions([buy])
        assert positions[0].last_note_type == "근거"
        assert positions[0].last_note == "기술적 분석 신호"

    def test_realized_pnl_accumulated(self):
        b1 = make_trade(id="b1", trade_type="BUY", quantity=10, price=70000, traded_at=_dt("2024-01-01T09:00:00+09:00"))
        s1 = make_trade(id="s1", trade_type="SELL", quantity=5, avg_buy_price=70000.0, profit_loss=50000.0,
                        traded_at=_dt("2024-02-01T09:00:00+09:00"))
        positions, _ = build_positions([b1, s1])
        assert len(positions) == 1
        assert positions[0].realized_pnl == 50000.0

    def test_returns_lot_map_for_reuse(self):
        """lot_map 은 build_account_snapshots 에서 재사용되도록 외부에 노출된다."""
        b1 = make_trade(id="b1", trade_type="BUY", quantity=10, account_id="a1")
        b2 = make_trade(id="b2", trade_type="BUY", quantity=3, account_id="a2")
        _, lot_map = build_positions([b1, b2])
        assert len(lot_map) == 2
        # 모든 lot 의 account_id 는 str 로 보관되어 account.id (str 강제) 와 매칭 가능
        assert all(isinstance(lot.account_id, str) for lot in lot_map.values())
        running_qtys = sorted(lot.running_qty for lot in lot_map.values())
        assert running_qtys == [3.0, 10.0]


class TestMergeQuotes:
    def test_quote_updates_position(self):
        pos = Position(
            key="005930:KR",
            ticker="005930",
            country="KR",
            asset_name="삼성전자",
            exchange="",
            holding_quantity=10.0,
            avg_buy_price=70000.0,
            cost_basis=700000.0,
            realized_pnl=0.0,
            current_price=None,
            evaluation=None,
            unrealized_pnl=None,
            last_note_type=None,
            last_note=None,
            last_traded_at="2024-01-01T00:00:00+00:00",
        )
        quotes: QuoteMap = {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": "2024-01-15"}}
        updated = merge_quotes([pos], quotes)
        assert updated[0].current_price == 75000.0
        assert updated[0].evaluation == 750000.0
        assert pytest.approx(updated[0].unrealized_pnl) == 50000.0

    def test_missing_quote_leaves_none(self):
        pos = Position(
            key="AAPL:US",
            ticker="AAPL",
            country="US",
            asset_name="Apple",
            exchange="NASDAQ",
            holding_quantity=5.0,
            avg_buy_price=150.0,
            cost_basis=750.0,
            realized_pnl=0.0,
            current_price=None,
            evaluation=None,
            unrealized_pnl=None,
            last_note_type=None,
            last_note=None,
            last_traded_at="2024-01-01T00:00:00+00:00",
        )
        updated = merge_quotes([pos], {})
        assert updated[0].current_price is None


class TestBuildAccountSnapshots:
    def test_snapshot_with_quote(self):
        account = make_account(id="a1", cash_balance=500000.0)
        buy = make_trade(id="b1", account_id="a1", quantity=10, price=70000)
        _, lot_map = build_positions([buy])
        quotes: QuoteMap = {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": ""}}
        snapshots = build_account_snapshots([account], lot_map, quotes)
        assert len(snapshots) == 1
        assert snapshots[0].stock_evaluation == 750000.0
        assert snapshots[0].cash_balance == 500000.0
        assert snapshots[0].total_value == 1250000.0

    def test_snapshot_no_quotes(self):
        account = make_account(id="a1", cash_balance=1000000.0)
        buy = make_trade(id="b1", account_id="a1", quantity=10)
        _, lot_map = build_positions([buy])
        snapshots = build_account_snapshots([account], lot_map, {})
        assert snapshots[0].stock_evaluation == 0.0
        assert snapshots[0].total_value == 1000000.0

    def test_snapshot_uuid_account_id(self):
        """UUID account.id should match str trade.account_id (asyncpg returns UUID objects)."""
        uid = UUID("00000000-0000-0000-0000-000000000001")
        account = make_account(id=uid, cash_balance=500000.0)
        buy = make_trade(id="b1", account_id=str(uid), quantity=10, price=70000)
        _, lot_map = build_positions([buy])
        quotes: QuoteMap = {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": ""}}
        # account.id 가 UUID 객체여도 lot["account_id"] 는 str 로 보관되므로
        # build_account_snapshots 내부에서 str(account.id) 와 매칭됨
        snapshots = build_account_snapshots([account], lot_map, quotes)
        assert snapshots[0].stock_evaluation == 750000.0
        assert snapshots[0].total_value == 1250000.0


class TestBuildTotals:
    def test_basic_totals(self):
        pos = Position(
            key="005930:KR",
            ticker="005930",
            country="KR",
            asset_name="삼성전자",
            exchange="",
            holding_quantity=10.0,
            avg_buy_price=70000.0,
            cost_basis=700000.0,
            realized_pnl=0.0,
            current_price=75000.0,
            evaluation=750000.0,
            unrealized_pnl=50000.0,
            last_note_type=None,
            last_note=None,
            last_traded_at="2024-01-01T00:00:00+00:00",
        )
        account = make_account(cash_balance=500000.0)
        sell = make_trade(id="s1", trade_type="SELL", profit_loss=100000.0)
        pnl_map = build_pnl_map([sell])
        totals = build_totals([pos], [account], [sell], pnl_map)
        assert totals.total_evaluation == 750000.0
        assert totals.total_unrealized_pnl == 50000.0
        assert totals.total_cash == 500000.0
        assert totals.total_assets == 1250000.0
        assert totals.total_realized_pnl == 100000.0

    def test_missing_quote_listed(self):
        pos = Position(
            key="AAPL:US",
            ticker="AAPL",
            country="US",
            asset_name="Apple",
            exchange="NASDAQ",
            holding_quantity=5.0,
            avg_buy_price=150.0,
            cost_basis=750.0,
            realized_pnl=0.0,
            current_price=None,
            evaluation=None,
            unrealized_pnl=None,
            last_note_type=None,
            last_note=None,
            last_traded_at="2024-01-01T00:00:00+00:00",
        )
        account = make_account()
        totals = build_totals([pos], [account], [], {})
        assert "Apple" in totals.missing_quote_tickers
