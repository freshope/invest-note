"""순수 함수 단위 테스트 — domain/analysis/"""
import pytest

from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.analysis.period import parse_period, filter_by_period
from invest_note_api.domain.analysis.holding_period import compute_holding_days_map
from invest_note_api.domain.analysis.aggregate import compute_summary, AnalysisSummary
from invest_note_api.domain.analysis.concentration import (
    compute_concentration,
    ConcentrationData,
)
from invest_note_api.domain.analysis.profile import compute_profile
from invest_note_api.domain.analysis.rules import evaluate_rules, RuleInput
from invest_note_api.domain.portfolio import Position
from tests.conftest import dt as _dt


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


# --- period ---

class TestParsePeriod:
    def test_valid_values(self):
        for v in ("1m", "3m", "6m", "ytd", "all"):
            assert parse_period(v) == v

    def test_invalid_returns_all(self):
        assert parse_period(None) == "all"
        assert parse_period("") == "all"
        assert parse_period("99d") == "all"


class TestFilterByPeriod:
    def _make_trades(self):
        return [
            make_trade(id="old", traded_at=_dt("2024-01-01T00:00:00Z")),
            make_trade(id="mid", traded_at=_dt("2026-01-15T00:00:00Z")),
            make_trade(id="now", traded_at=_dt("2026-04-22T00:00:00Z")),
        ]

    def test_all_returns_all(self):
        trades = self._make_trades()
        result = filter_by_period(trades, "all")
        assert len(result) == 3

    def test_1m_excludes_old(self):
        trades = self._make_trades()
        result = filter_by_period(trades, "1m")
        ids = {t.id for t in result}
        assert "old" not in ids
        assert "mid" not in ids
        assert "now" in ids

    def test_ytd_includes_this_year(self):
        trades = self._make_trades()
        result = filter_by_period(trades, "ytd")
        ids = {t.id for t in result}
        assert "old" not in ids
        assert "now" in ids


# --- holding_period ---

class TestComputeHoldingDaysMap:
    def test_basic_single_sell(self):
        buy = make_trade(id="b1", trade_type="BUY", quantity=10.0, traded_at=_dt("2026-01-01T09:00:00+09:00"))
        sell = make_trade(
            id="s1",
            trade_type="SELL",
            quantity=10.0,
            holding_days=10,
            traded_at=_dt("2026-01-11T09:00:00+09:00"),
        )
        result = compute_holding_days_map([buy, sell])
        assert result["s1"] == 10

    def test_empty_trades(self):
        assert compute_holding_days_map([]) == {}

    def test_no_buy_before_sell(self):
        sell = make_trade(id="s1", trade_type="SELL", quantity=5.0)
        result = compute_holding_days_map([sell])
        assert result == {}

    def test_only_buys(self):
        buy = make_trade(id="b1", trade_type="BUY")
        result = compute_holding_days_map([buy])
        assert result == {}


# --- aggregate ---

class TestComputeSummary:
    def test_empty_trades(self):
        s = compute_summary([], {}, {})
        assert s.total_trades == 0
        assert s.sell_trades == 0
        assert s.win_rate == 0.0
        assert s.total_profit_loss == 0.0

    def test_win_rate(self):
        buy = make_trade(id="b1", trade_type="BUY")
        sell_win = make_trade(id="s1", trade_type="SELL", result="SUCCESS")
        sell_fail = make_trade(id="s2", trade_type="SELL", result="FAIL")
        pnl = {"s1": 100.0, "s2": -50.0}
        s = compute_summary([buy, sell_win, sell_fail], pnl, {})
        assert s.sell_trades == 2
        assert s.win_rate == 50.0
        assert s.total_profit_loss == 50.0

    def test_by_strategy(self):
        buy = make_trade(id="b1", trade_type="BUY", strategy_type="SWING", traded_at=_dt("2026-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", strategy_type="SWING", result="SUCCESS", traded_at=_dt("2026-01-10T09:00:00+09:00"))
        s = compute_summary([buy, sell], {"s1": 200.0}, {"s1": 9})
        assert len(s.by_strategy) == 1
        assert s.by_strategy[0].type == "SWING"
        assert s.by_strategy[0].win_rate == 100.0
        assert s.strategy_adherence_rate == 100.0

    def test_strategy_adherence_deviated(self):
        buy = make_trade(id="b1", trade_type="BUY", strategy_type="LONG_TERM", traded_at=_dt("2026-01-01T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", strategy_type="LONG_TERM", result="SUCCESS", traded_at=_dt("2026-01-02T09:00:00+09:00"))
        s = compute_summary([buy, sell], {"s1": 200.0}, {"s1": 1})
        assert s.by_strategy[0].type == "LONG_TERM"
        assert s.strategy_adherence_rate == 0.0
        deviated = next(a for a in s.by_strategy_adherence if a.type == "DEVIATED")
        assert deviated.count == 1
        assert deviated.win_rate == 100.0

    def test_by_strategy_uses_sell_strategy_without_holding_days(self):
        sell = make_trade(id="s1", trade_type="SELL", strategy_type="SWING", result="SUCCESS")
        s = compute_summary([sell], {"s1": 200.0}, {})
        assert s.by_strategy[0].type == "SWING"
        assert s.by_strategy[0].avg_holding_days == 0.0
        assert s.strategy_adherence_rate == 0.0

    def test_by_strategy_uses_sell_strategy(self):
        b1 = make_trade(id="b1", trade_type="BUY", strategy_type="SCALPING", quantity=4, traded_at=_dt("2026-01-01T09:00:00+09:00"))
        b2 = make_trade(id="b2", trade_type="BUY", strategy_type="SWING", quantity=6, traded_at=_dt("2026-01-02T09:00:00+09:00"))
        sell = make_trade(id="s1", trade_type="SELL", strategy_type="LONG_TERM", quantity=10, result="SUCCESS", traded_at=_dt("2026-01-10T09:00:00+09:00"))
        s = compute_summary([b1, b2, sell], {"s1": 200.0}, {"s1": 8})
        assert s.by_strategy[0].type == "LONG_TERM"

    def test_strategy_adherence_uses_stored_holding_days(self):
        buy = make_trade(
            id="b1",
            trade_type="BUY",
            ticker_symbol="",
            strategy_type="SWING",
            traded_at=_dt("2026-01-01T09:00:00+09:00"),
        )
        sell = make_trade(
            id="s1",
            trade_type="SELL",
            ticker_symbol="005930",
            strategy_type="SWING",
            result="SUCCESS",
            holding_days=9,
            traded_at=_dt("2026-01-10T09:00:00+09:00"),
        )
        s = compute_summary([buy, sell], {"s1": 200.0}, {})
        assert s.by_strategy[0].type == "SWING"
        assert s.by_strategy[0].avg_holding_days == 9
        assert s.strategy_adherence_rate == 100.0

    def test_strategy_adherence_rate_uses_period_sells_only(self):
        old_buy = make_trade(
            id="b-old",
            trade_type="BUY",
            strategy_type="LONG_TERM",
            traded_at=_dt("2025-01-01T09:00:00+09:00"),
        )
        old_sell = make_trade(
            id="s-old",
            trade_type="SELL",
            strategy_type="LONG_TERM",
            traded_at=_dt("2025-01-02T09:00:00+09:00"),
        )
        recent_buy = make_trade(
            id="b-recent",
            trade_type="BUY",
            strategy_type="SCALPING",
            traded_at=_dt("2026-01-01T09:00:00+09:00"),
        )
        recent_sell = make_trade(
            id="s-recent",
            trade_type="SELL",
            strategy_type="SCALPING",
            traded_at=_dt("2026-01-01T10:00:00+09:00"),
        )
        # all_trades 인자는 더 이상 받지 않음 — period 내 sells만으로도 동일 결과
        _ = (old_buy, old_sell)
        s = compute_summary(
            [recent_buy, recent_sell],
            {"s-old": -100.0, "s-recent": 100.0},
            {"s-old": 1, "s-recent": 0},
        )
        assert s.strategy_adherence_rate == 100.0

    def test_by_emotion(self):
        # SELL에 저장된 emotion만 카운트 (BUY는 무시) — mutation 시 자동 산출이 SELL에 채워짐
        buy = make_trade(id="t1", trade_type="BUY", emotion="FOMO")
        sell = make_trade(id="t2", trade_type="SELL", emotion="FOMO", result="FAIL")
        s = compute_summary([buy, sell], {"t2": -100.0}, {})
        fomo = next(e for e in s.by_emotion if e.type == "FOMO")
        assert fomo.count == 1
        assert fomo.win_rate == 0.0

    def test_by_tag_uses_sell_stored_tags(self):
        # SELL의 저장된 reasoning_tags만 사용 (BUY는 무시)
        buy = make_trade(id="b1", trade_type="BUY", reasoning_tags=["FUNDAMENTAL"])
        sell = make_trade(
            id="s1",
            trade_type="SELL",
            reasoning_tags=["TECHNICAL", "NEWS"],
            result="SUCCESS",
        )
        s = compute_summary([buy, sell], {"s1": 100.0}, {})
        tags = {t.tag: t for t in s.by_tag}
        assert "TECHNICAL" in tags
        assert "NEWS" in tags
        assert "FUNDAMENTAL" not in tags
        assert tags["TECHNICAL"].count == 1
        assert tags["TECHNICAL"].win_rate == 100.0

    def test_meta_rates(self):
        buy_no_tag = make_trade(id="b1", trade_type="BUY", reasoning_tags=[])
        buy_feeling = make_trade(id="b2", trade_type="BUY", reasoning_tags=["FEELING"])
        sell_with_reflection = make_trade(id="s1", trade_type="SELL", sell_reason="good", result="SUCCESS")
        sell_no_result = make_trade(id="s2", trade_type="SELL")
        s = compute_summary([buy_no_tag, buy_feeling, sell_with_reflection, sell_no_result], {"s1": 100.0}, {})
        assert s.missing_tag_rate == 50.0
        assert s.feeling_rate == 50.0
        assert s.reflection_rate == 50.0
        assert s.result_input_rate == 50.0

    def test_by_emotion_includes_untagged_bucket(self):
        # emotion 미입력 SELL이 통째 누락되어 합계가 어긋나던 버그 회귀 방지.
        sell_tagged = make_trade(id="s1", trade_type="SELL", emotion="FOMO", result="FAIL")
        sell_untagged = make_trade(id="s2", trade_type="SELL", emotion=None, result="SUCCESS")
        s = compute_summary([sell_tagged, sell_untagged], {"s1": -100.0, "s2": 50.0}, {})
        emotions = {e.type: e for e in s.by_emotion}
        assert "UNTAGGED" in emotions
        assert emotions["UNTAGGED"].count == 1
        assert emotions["UNTAGGED"].sum_pnl == 50.0

    def test_by_tag_includes_untagged_bucket(self):
        # reasoning_tags=[]인 SELL이 통째 누락되어 합계가 어긋나던 버그 회귀 방지.
        sell_tagged = make_trade(id="s1", trade_type="SELL", reasoning_tags=["TECHNICAL"], result="SUCCESS")
        sell_untagged = make_trade(id="s2", trade_type="SELL", reasoning_tags=[], result="FAIL")
        s = compute_summary([sell_tagged, sell_untagged], {"s1": 100.0, "s2": -30.0}, {})
        tags = {t.tag: t for t in s.by_tag}
        assert "UNTAGGED" in tags
        assert tags["UNTAGGED"].count == 1
        assert tags["UNTAGGED"].sum_pnl == -30.0

    def test_sum_pnl_equals_total_profit_loss(self):
        # 화면 상의 항목별 sumPnL 합계가 총 실현손익과 일치해야 한다 (byTag 제외).
        # byTag는 다중 태그로 인해 중복 합산되므로 별도 검증.
        sells = [
            make_trade(
                id="s1",
                trade_type="SELL",
                strategy_type="SWING",
                emotion="CALM",
                reasoning_tags=["TECHNICAL"],
                result="SUCCESS",
            ),
            make_trade(
                id="s2",
                trade_type="SELL",
                strategy_type=None,
                emotion=None,
                reasoning_tags=[],
                result=None,
            ),
            make_trade(
                id="s3",
                trade_type="SELL",
                strategy_type="LONG_TERM",
                emotion="FOMO",
                reasoning_tags=["NEWS", "FUNDAMENTAL"],
                result="FAIL",
                holding_days=5,
            ),
        ]
        pnl = {"s1": 100.0, "s2": -50.0, "s3": -200.0}
        s = compute_summary(sells, pnl, {})
        assert s.total_profit_loss == pytest.approx(-150.0)
        assert sum(e.sum_pnl for e in s.by_emotion) == pytest.approx(s.total_profit_loss)
        assert sum(x.sum_pnl for x in s.by_strategy) == pytest.approx(s.total_profit_loss)
        assert sum(x.sum_pnl for x in s.by_strategy_adherence) == pytest.approx(s.total_profit_loss)
        # byTag: s3가 두 태그를 가지므로 -200이 두 번 합산 → 합계가 더 작음(중복).
        # 다중 태그 거래로 인해 합계가 totalProfitLoss와 다른 것이 정상.
        assert sum(t.sum_pnl for t in s.by_tag) != pytest.approx(s.total_profit_loss)


# --- concentration ---

def _make_position(key: str, cost: float, country: str = "KR", evaluation: float | None = None) -> Position:
    ticker, _ = key.split(":")
    return Position(
        key=key,
        ticker=ticker,
        country=country,
        asset_name=ticker,
        exchange="",
        holding_quantity=1.0,
        avg_buy_price=cost,
        cost_basis=cost,
        realized_pnl=0.0,
        current_price=None,
        evaluation=evaluation,
        unrealized_pnl=None,
        last_note_type=None,
        last_note=None,
        last_traded_at="2026-01-01T00:00:00Z",
    )


class TestComputeConcentration:
    def test_empty(self):
        result = compute_concentration([], [])
        assert result.hhi == 0.0
        assert result.top3 == []

    def test_single_position(self):
        pos = _make_position("005930:KR", 1000.0)
        result = compute_concentration([pos], [])
        assert result.hhi == pytest.approx(1.0)
        assert len(result.top3) == 1
        assert result.top3[0]["weight"] == pytest.approx(1.0)

    def test_equal_two_positions(self):
        pos1 = _make_position("A:KR", 500.0)
        pos2 = _make_position("B:KR", 500.0)
        result = compute_concentration([pos1, pos2], [])
        assert result.hhi == pytest.approx(0.5)

    def test_uses_evaluation_over_cost_basis(self):
        pos = _make_position("A:KR", 500.0, evaluation=1000.0)
        result = compute_concentration([pos], [])
        assert result.hhi == pytest.approx(1.0)


# --- profile ---

class TestComputeProfile:
    def test_empty(self):
        profile, rates = compute_profile([], 0.0, {})
        assert profile.diversification == 50.0
        assert rates.holding_days == 0.0

    def test_tempo_long_term(self):
        sells = [
            make_trade(id=f"s{i}", trade_type="SELL", strategy_type="LONG_TERM")
            for i in range(5)
        ]
        holding_map = {f"s{i}": 120 for i in range(5)}
        profile, _ = compute_profile(sells, 0.3, holding_map)
        assert profile.tempo == 100.0

    def test_tempo_half_score_at_30_days(self):
        sells = [make_trade(id=f"s{i}", trade_type="SELL") for i in range(4)]
        holding_map = {f"s{i}": 30 for i in range(4)}
        profile, _ = compute_profile(sells, 0.3, holding_map)
        assert profile.tempo == 50.0

    def test_tempo_short_holding_low_score(self):
        sells = [make_trade(id=f"s{i}", trade_type="SELL") for i in range(4)]
        holding_map = {f"s{i}": 1 for i in range(4)}
        profile, _ = compute_profile(sells, 0.3, holding_map)
        assert profile.tempo == pytest.approx((1 / 60) * 100)

    def test_emotion_stability_unstable(self):
        trades = [
            make_trade(id="t1", emotion="FOMO"),
            make_trade(id="t2", emotion="FOMO"),
            make_trade(id="t3", emotion="CALM"),
            make_trade(id="t4", emotion="CALM"),
        ]
        profile, _ = compute_profile(trades, 0.0, {})
        assert profile.emotion_stability == 50.0


# --- rules ---

def _make_summary(**kwargs) -> AnalysisSummary:
    from invest_note_api.domain.analysis.aggregate import AnalysisSummary
    defaults = dict(
        total_trades=10,
        sell_trades=5,
        win_rate=50.0,
        total_profit_loss=0.0,
        by_strategy=[],
        by_emotion=[],
        by_tag=[],
        missing_tag_rate=0.0,
        feeling_rate=0.0,
        reflection_rate=50.0,
        result_input_rate=80.0,
    )
    defaults.update(kwargs)
    return AnalysisSummary(**defaults)


class TestEvaluateRules:
    def test_empty_no_suggestions(self):
        inp: RuleInput = {"summary": _make_summary()}
        result = evaluate_rules(inp)
        assert isinstance(result, list)

    def test_losing_strategy_triggers(self):
        from invest_note_api.domain.analysis.aggregate import StrategyStats
        worst = StrategyStats(type="SCALPING", count=6, result_count=4, win_rate=20.0, sum_pnl=-100.0, avg_holding_days=0.5)
        summary = _make_summary(by_strategy=[worst])
        inp: RuleInput = {"summary": summary}
        result = evaluate_rules(inp)
        ids = [s.id for s in result]
        assert "losing_strategy" in ids
        critical = next(s for s in result if s.id == "losing_strategy")
        assert critical.severity == "critical"

    def test_severity_order(self):
        from invest_note_api.domain.analysis.aggregate import StrategyStats, EmotionStats
        worst_strat = StrategyStats(type="SWING", count=6, result_count=4, win_rate=10.0, sum_pnl=-100.0, avg_holding_days=10.0)
        fomo_emotion = EmotionStats(type="FOMO", count=6, result_count=5, win_rate=10.0, sum_pnl=-50.0)
        summary = _make_summary(by_strategy=[worst_strat], by_emotion=[fomo_emotion], feeling_rate=50.0, total_trades=10)
        inp: RuleInput = {"summary": summary}
        result = evaluate_rules(inp)
        if len(result) >= 2:
            severity_order = {"critical": 0, "warn": 1, "info": 2}
            for a, b in zip(result, result[1:]):
                assert severity_order[a.severity] <= severity_order[b.severity]

    def test_fomo_low_winrate(self):
        from invest_note_api.domain.analysis.aggregate import EmotionStats
        fomo = EmotionStats(type="FOMO", count=6, result_count=5, win_rate=20.0, sum_pnl=-50.0)
        summary = _make_summary(by_emotion=[fomo])
        inp: RuleInput = {"summary": summary}
        result = evaluate_rules(inp)
        assert any(s.id == "emotion_fomo_low_winrate" for s in result)

    def test_high_winrate_triggers(self):
        summary = _make_summary(sell_trades=6, win_rate=70.0, result_input_rate=80.0)
        inp: RuleInput = {"summary": summary}
        result = evaluate_rules(inp)
        assert any(s.id == "high_winrate" for s in result)

    def test_concentration_high_triggers(self):
        conc = ConcentrationData(
            hhi=0.6,
            top3=[{"asset": "A", "weight": 0.6}],
            by_country=[],
            by_market=[],
        )
        inp: RuleInput = {"summary": _make_summary(), "concentration": conc}
        result = evaluate_rules(inp)
        assert any(s.id == "concentration_high" for s in result)

    def test_round_half_up(self):
        """Math.round HALF_UP — 0.5 -> 1, not 0."""
        from invest_note_api.domain.analysis.rules import _round
        assert _round(0.5) == 1
        assert _round(1.5) == 2
        assert _round(2.5) == 3
