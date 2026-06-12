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
from invest_note_api.domain.realized_pnl import (
    build_pnl_map,
    compute_group_pnl,
    trade_to_group_key,
)
from invest_note_api.domain.analysis.concentration import compute_concentration


def make_position(**over) -> Position:
    """Position 팩토리 — 새 통화 필드 포함, KR 기본. over 로 개별 필드 덮어쓰기."""
    country = over.pop("country", "KR")
    defaults = dict(
        key=over.get("key", "005930:KR"),
        ticker="005930",
        country=country,
        currency="USD" if country == "US" else "KRW",
        asset_name="삼성전자",
        exchange="",
        holding_quantity=10.0,
        avg_buy_price=70000.0,
        avg_buy_price_native=70000.0,
        cost_basis=700000.0,
        cost_basis_native=700000.0,
        realized_pnl=0.0,
        current_price=None,
        evaluation=None,
        evaluation_native=None,
        unrealized_pnl=None,
        last_note_type=None,
        last_note=None,
        last_traded_at="2024-01-01T00:00:00+00:00",
        account_ids=["a1"],
    )
    defaults.update(over)
    return Position(**defaults)


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

    def test_same_day_buy_sell_buy_sell_buy_first(self):
        """시각 없는 일괄 등록의 동률 traded_at 케이스 — sort_for_calc 의 BUY-first tiebreaker.

        NHN 사용자 시나리오: 2025-06-18 BUY 29 + BUY 93 + SELL 61, 2025-06-25 SELL 61.
        입력 순열에 무관하게 최종 보유 0주 (== 포지션 비어 있음) 이어야 한다.
        sort_by_traded_at 시절에는 SELL 이 먼저 매칭되면 32주가 잔류했다.
        """
        same_day = _dt("2025-06-18T00:00:00Z")
        later = _dt("2025-06-25T00:00:00Z")
        # 입력 순서 의도적으로 섞기 — sort_for_calc 가 결정적으로 BUY 먼저 정렬해야 함
        trades = [
            make_trade(id="s1", trade_type="SELL", ticker_symbol="NHN", asset_name="NHN",
                       quantity=61, price=27550, traded_at=same_day, avg_buy_price=28361.0738),
            make_trade(id="b1", trade_type="BUY", ticker_symbol="NHN", asset_name="NHN",
                       quantity=29, price=28400, traded_at=same_day),
            make_trade(id="b2", trade_type="BUY", ticker_symbol="NHN", asset_name="NHN",
                       quantity=93, price=28350, traded_at=same_day),
            make_trade(id="s2", trade_type="SELL", ticker_symbol="NHN", asset_name="NHN",
                       quantity=61, price=32000, traded_at=later, avg_buy_price=28362.6993),
        ]
        positions, _ = build_positions(trades)
        assert positions == [], f"holding 0 expected, got {positions}"


class TestMergeQuotes:
    def test_quote_updates_position(self):
        pos = make_position(
            key="005930:KR", holding_quantity=10.0, avg_buy_price=70000.0, cost_basis=700000.0
        )
        quotes: QuoteMap = {"005930:KR": {"price": 75000.0, "currency": "KRW", "as_of": "2024-01-15"}}
        updated = merge_quotes([pos], quotes)
        assert updated[0].current_price == 75000.0
        assert updated[0].evaluation == 750000.0
        assert pytest.approx(updated[0].unrealized_pnl) == 50000.0

    def test_missing_quote_leaves_none(self):
        pos = make_position(
            key="AAPL:US", country="US", ticker="AAPL", asset_name="Apple", exchange="NASDAQ",
            holding_quantity=5.0, avg_buy_price=750.0, cost_basis=750.0,
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

    def test_snapshot_holdings_single_account(self):
        """holdings 에 running_qty>0 종목 {key, quantity} 가 담긴다 (key=ticker:country)."""
        account = make_account(id="a1", cash_balance=500000.0)
        buy = make_trade(id="b1", account_id="a1", quantity=10, price=70000)
        _, lot_map = build_positions([buy])
        snapshots = build_account_snapshots([account], lot_map, {})
        holdings = snapshots[0].holdings
        assert len(holdings) == 1
        assert holdings[0].key == "005930:KR"
        assert holdings[0].quantity == 10.0

    def test_snapshot_holdings_multi_account_same_ticker(self):
        """동일 종목이 여러 계좌에 걸칠 때 각 계좌 snapshot 은 자기 계좌 수량만 담는다.

        positions 의 holding_quantity(8) 는 합산값이지만 holdings 는 계좌별 분배(5/3) —
        FE 가 계좌별 totalValue 를 재계산하려면 이 분배가 필수다.
        """
        a1 = make_account(id="a1", cash_balance=0.0)
        a2 = make_account(id="a2", cash_balance=0.0)
        b1 = make_trade(id="b1", account_id="a1", quantity=5, price=70000)
        b2 = make_trade(id="b2", account_id="a2", quantity=3, price=70000)
        _, lot_map = build_positions([b1, b2])
        snapshots = build_account_snapshots([a1, a2], lot_map, {})
        by_id = {s.account.id: s for s in snapshots}
        assert [h.quantity for h in by_id["a1"].holdings] == [5.0]
        assert [h.quantity for h in by_id["a2"].holdings] == [3.0]
        assert by_id["a1"].holdings[0].key == "005930:KR"
        assert by_id["a2"].holdings[0].key == "005930:KR"

    def test_snapshot_holdings_excludes_zero_qty(self):
        """전량 매도(running_qty=0)된 lot 은 holdings 에 나타나지 않는다."""
        account = make_account(id="a1", cash_balance=1000000.0)
        buy = make_trade(id="b1", account_id="a1", trade_type="BUY", quantity=10,
                         traded_at=_dt("2024-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", account_id="a1", trade_type="SELL", quantity=10,
                          avg_buy_price=70000.0, profit_loss=0.0,
                          traded_at=_dt("2024-02-01T09:00:00+09:00"))
        _, lot_map = build_positions([buy, sell])
        snapshots = build_account_snapshots([account], lot_map, {})
        assert snapshots[0].holdings == []

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
        pos = make_position(current_price=75000.0, evaluation=750000.0, unrealized_pnl=50000.0)
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
        pos = make_position(
            key="AAPL:US", country="US", ticker="AAPL", asset_name="Apple", exchange="NASDAQ",
            holding_quantity=5.0, current_price=None, evaluation=None,
        )
        account = make_account()
        totals = build_totals([pos], [account], [], {})
        assert "Apple" in totals.missing_quote_tickers


class TestCurrencyRedesign:
    """거래 시점 환율 저장 + KRW 정규화 — 원가·실현손익 KRW 고정, 평가액만 현재 환율."""

    def test_cost_fixed_krw_via_exchange_rate(self):
        # US BUY $200×10 @1500 → 원가 3,000,000 KRW 고정(저장 환율) + native(USD) 보조.
        buy = make_trade(
            id="b-us", trade_type="BUY", ticker_symbol="AAPL", asset_name="Apple",
            country_code="US", quantity=10.0, price=200.0, exchange_rate=1500.0,
        )
        positions, _ = build_positions([buy])
        p = positions[0]
        assert p.currency == "USD"
        assert p.cost_basis == 3_000_000.0        # KRW 고정
        assert p.cost_basis_native == 2000.0      # USD ($200×10)
        assert p.avg_buy_price == 300000.0        # KRW/주
        assert p.avg_buy_price_native == 200.0    # USD/주

    def test_eval_current_rate_cost_invariant(self):
        # 시금석: 현재 환율이 변해도 원가는 불변, 평가액만 변동.
        buy = make_trade(
            id="b-us", trade_type="BUY", ticker_symbol="AAPL", asset_name="Apple",
            country_code="US", quantity=10.0, price=200.0, exchange_rate=1500.0,
        )
        positions, _ = build_positions([buy])
        quotes: QuoteMap = {"AAPL:US": {"price": 220.0, "currency": "USD", "as_of": ""}}
        merged = merge_quotes(positions, quotes, usdkrw=1530.0)
        p = merged[0]
        assert p.evaluation == 3_366_000.0        # 220×10×1530
        assert p.evaluation_native == 2200.0      # 220×10 (USD)
        assert p.cost_basis == 3_000_000.0        # 현재 환율과 무관하게 불변
        assert p.unrealized_pnl == 366_000.0
        # 환율 1600 으로 바뀌어도 원가 불변, 평가액만 변동
        merged2 = merge_quotes(positions, quotes, usdkrw=1600.0)
        assert merged2[0].cost_basis == 3_000_000.0
        assert merged2[0].evaluation == 220.0 * 10 * 1600

    def test_realized_pnl_krw_fixed(self):
        # BUY $200×10 @1500, SELL $210×10 @1520 → 실현손익 KRW.
        buy = make_trade(
            id="b", trade_type="BUY", ticker_symbol="AAPL", asset_name="Apple",
            country_code="US", quantity=10.0, price=200.0, exchange_rate=1500.0,
            traded_at=_dt("2024-01-01T09:00:00+09:00"),
        )
        sell = make_trade(
            id="s", trade_type="SELL", ticker_symbol="AAPL", asset_name="Apple",
            country_code="US", quantity=10.0, price=210.0, exchange_rate=1520.0,
            traded_at=_dt("2024-02-01T09:00:00+09:00"),
        )
        pnl = compute_group_pnl([buy, sell], trade_to_group_key(buy))
        # KRW: 210×10×1520 - 200×10×1500 = 3,192,000 - 3,000,000 = 192,000
        assert pnl["s"].profit_loss == pytest.approx(192_000.0)
        assert pnl["s"].avg_buy_price == pytest.approx(300000.0)  # KRW 평단

    def test_merge_quotes_us_no_fx_eval_none_cost_kept(self):
        buy = make_trade(
            id="b-us", trade_type="BUY", ticker_symbol="AAPL", asset_name="Apple",
            country_code="US", quantity=10.0, price=200.0, exchange_rate=1500.0,
        )
        positions, _ = build_positions([buy])
        quotes: QuoteMap = {"AAPL:US": {"price": 220.0, "currency": "USD", "as_of": ""}}
        merged = merge_quotes(positions, quotes, usdkrw=None)  # 환율 미수신
        assert merged[0].evaluation is None       # KRW 평가 미상
        assert merged[0].cost_basis == 3_000_000.0  # 원가는 유지

    def test_build_account_snapshots_us_current_rate(self):
        buy_kr = make_trade(id="b-kr", account_id="a1", ticker_symbol="005930",
                            country_code="KR", quantity=10.0, price=70000.0)
        buy_us = make_trade(id="b-us", account_id="a1", ticker_symbol="AAPL", asset_name="Apple",
                            country_code="US", quantity=10.0, price=200.0, exchange_rate=1500.0)
        _, lot_map = build_positions([buy_kr, buy_us])
        quotes: QuoteMap = {
            "005930:KR": {"price": 70000.0, "currency": "KRW", "as_of": ""},
            "AAPL:US": {"price": 220.0, "currency": "USD", "as_of": ""},
        }
        account = make_account(id="a1", cash_balance=0.0)
        snaps = build_account_snapshots([account], lot_map, quotes, usdkrw=1530.0)
        # KR 70,000×10 + US 220×10×1,530(현재환율) = 700,000 + 3,366,000 = 4,066,000
        assert snaps[0].stock_evaluation == 4_066_000.0

    def test_concentration_krw_weights(self):
        # cost_basis 가 이미 KRW → US 원가 3,000,000 이 KR 700,000 보다 큼 → US top.
        kr = make_position(evaluation=700000.0, cost_basis=700000.0)
        us = make_position(
            key="AAPL:US", country="US", ticker="AAPL", asset_name="Apple",
            evaluation=1_500_000.0, cost_basis=3_000_000.0,
        )
        conc = compute_concentration([kr, us], [])
        assert conc.top3[0]["asset"] == "Apple"
