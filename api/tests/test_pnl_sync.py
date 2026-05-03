"""recalc_group_pnl — 변경 row만 UPDATE 발행하는지 검증."""
from datetime import datetime, timezone
from typing import Any


from invest_note_api.db_ops.pnl_sync import recalc_group_pnl
from invest_note_api.domain.realized_pnl import TradeGroupKey
from invest_note_api.domain.trade_types import Trade


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


def _key() -> TradeGroupKey:
    return TradeGroupKey(ticker="005930", asset_name="삼성전자", country="KR", account_id="a1")


class FakeConn:
    """executemany 호출을 캡처하는 최소 fake."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    async def executemany(self, sql: str, rows: list[Any]) -> None:
        self.calls.append((sql, rows))


class TestRecalcGroupPnLChangedOnly:
    async def test_skip_when_no_sells(self) -> None:
        """SELL이 없으면 executemany 미호출."""
        conn = FakeConn()
        trades = [make_trade(id="b1", trade_type="BUY")]
        await recalc_group_pnl(conn, trades, _key())
        assert conn.calls == []

    async def test_first_recalc_updates_all_new_sells(self) -> None:
        """기존 PnL 필드가 NULL인 SELL은 항상 UPDATE 대상."""
        conn = FakeConn()
        trades = [
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=10,
                       traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="s1", trade_type="SELL", price=80000, quantity=10,
                       traded_at=_dt("2024-02-01T09:00:00+09:00")),
        ]
        await recalc_group_pnl(conn, trades, _key())
        assert len(conn.calls) == 1
        sql, rows = conn.calls[0]
        assert len(rows) == 1
        # 마지막 파라미터가 sell_id
        assert rows[0][-1] == "s1"

    async def test_skip_when_existing_values_match(self) -> None:
        """직전 recalc 결과와 동일하면 executemany 미호출."""
        conn = FakeConn()
        trades = [
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=10,
                       traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(
                id="s1",
                trade_type="SELL",
                price=80000,
                quantity=10,
                traded_at=_dt("2024-02-01T09:00:00+09:00"),
                profit_loss=100000.0,
                avg_buy_price=70000.0,
                holding_days=31,
                strategy_type="UNKNOWN",
                reasoning_tags=[],
                emotion=None,
                result="SUCCESS",
            ),
        ]
        await recalc_group_pnl(conn, trades, _key())
        assert conn.calls == []

    async def test_only_changed_row_is_updated(self) -> None:
        """SELL 2건 중 메타가 다른 1건만 UPDATE에 포함."""
        conn = FakeConn()
        # BUY 2개, SELL 2개 — 둘 다 직전 값으로 채워져 있는데 s2의 emotion만 stale
        trades = [
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=5,
                       traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(id="b2", trade_type="BUY", price=70000, quantity=5,
                       reasoning_tags=["NEWS"], emotion="CONFIDENT",
                       traded_at=_dt("2024-01-15T09:00:00+09:00")),
            make_trade(
                id="s1",
                trade_type="SELL",
                price=80000,
                quantity=5,
                traded_at=_dt("2024-01-10T09:00:00+09:00"),
                profit_loss=50000.0,
                avg_buy_price=70000.0,
                holding_days=9,
                strategy_type="UNKNOWN",
                reasoning_tags=[],
                emotion=None,
                result="SUCCESS",
            ),
            make_trade(
                id="s2",
                trade_type="SELL",
                price=80000,
                quantity=5,
                traded_at=_dt("2024-02-01T09:00:00+09:00"),
                profit_loss=50000.0,
                avg_buy_price=70000.0,
                holding_days=17,
                strategy_type="UNKNOWN",
                reasoning_tags=[],  # stale — 새 계산은 ["NEWS"] 반환
                emotion=None,       # stale — 새 계산은 "CONFIDENT"
                result="SUCCESS",
            ),
        ]
        await recalc_group_pnl(conn, trades, _key())
        assert len(conn.calls) == 1
        _, rows = conn.calls[0]
        assert len(rows) == 1
        assert rows[0][-1] == "s2"

    async def test_float_microdiff_does_not_trigger_update(self) -> None:
        """DB round-trip 후 미세 부동소수 오차는 변경으로 보지 않음."""
        conn = FakeConn()
        trades = [
            make_trade(id="b1", trade_type="BUY", price=70000, quantity=10,
                       traded_at=_dt("2024-01-01T09:00:00+09:00")),
            make_trade(
                id="s1",
                trade_type="SELL",
                price=80000,
                quantity=10,
                traded_at=_dt("2024-02-01T09:00:00+09:00"),
                profit_loss=100000.0 + 1e-12,
                avg_buy_price=70000.0 - 1e-12,
                holding_days=31,
                strategy_type="UNKNOWN",
                reasoning_tags=[],
                emotion=None,
                result="SUCCESS",
            ),
        ]
        await recalc_group_pnl(conn, trades, _key())
        assert conn.calls == []
