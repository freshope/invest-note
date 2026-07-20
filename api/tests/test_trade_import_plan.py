"""domain.trade_import_plan 단위 테스트 — preview·commit 이 공유하는 순수 결정 로직.

이 결정(insert/merge/noop/intrabatch/reject/그룹제외)이 preview 카운트와 commit 적용
양쪽에 그대로 쓰이므로, 여기의 분류가 preview≠commit 드리프트를 막는 단일 지점이다.
"""

from datetime import date, datetime, timezone

from invest_note_api.domain.realized_pnl import TradeGroupKey
from invest_note_api.domain.trade_import_plan import GroupPlan, plan_import_group
from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.trade_utils import kst_date_to_utc
from invest_note_api.routers.trades import _preview_counts

NOW = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _row(*, ticker="005930", name="삼성전자", tt="BUY", qty=10.0, px=70000.0,
         kst="2024-01-10", commission=0.0, tax=0.0, country="KR", rate=1.0, exchange=""):
    return {
        "asset_name": name, "ticker_symbol": ticker, "market_type": "STOCK",
        "trade_type": tt, "price": px, "quantity": qty, "traded_at_kst": kst,
        "traded_at_kst_full": None, "commission": commission, "tax": tax,
        "country_code": country, "exchange_rate": rate, "exchange": exchange,
    }


def _gk(*, account="a1", ticker="005930", name="삼성전자", country="KR"):
    return TradeGroupKey(account_id=account, ticker=ticker, asset_name=name, country=country)


def _existing(*, id_="e1", tt="BUY", qty=10.0, px=70000.0, kst="2024-01-10",
              account="a1", ticker="005930", name="삼성전자", commission=0.0):
    return Trade(
        id=id_, user_id="u", account_id=account, asset_name=name, ticker_symbol=ticker,
        market_type="STOCK", trade_type=tt, price=px, quantity=qty, total_amount=px * qty,
        traded_at=kst_date_to_utc(date.fromisoformat(kst)), commission=commission, tax=0.0,
        country_code="KR", exchange="", created_at=NOW, updated_at=NOW,
    )


class TestPlanImportGroup:
    def test_insert_only(self):
        plan = plan_import_group(_gk(), [_row()], [], now=NOW)
        assert len(plan.inserts) == 1
        assert plan.merges == []
        assert plan.excluded_reason is None
        assert plan.inserts[0]["traded_at_utc"] is not None  # apply 용 부가 필드

    def test_noop_skip_matches_existing_identical(self):
        # 기존과 완전 동일 → noop(merge 아님). dup_count 에는 잡히되 갱신은 아님.
        plan = plan_import_group(_gk(), [_row()], [_existing()], now=NOW)
        assert plan.inserts == []
        assert plan.merges == []
        assert plan.noop_skips == 1
        assert plan.matched_existing == 1

    def test_merge_when_amount_differs(self):
        # 시그니처 동일(수수료만 다름) → merge.
        plan = plan_import_group(_gk(), [_row(commission=99)], [_existing(commission=5)], now=NOW)
        assert plan.inserts == []
        assert len(plan.merges) == 1
        assert plan.matched_existing == 1

    def test_intrabatch_dup_counts_one_insert(self):
        # 같은 파일 안 동일 행 2건 → insert 1 + intrabatch skip 1(빈 계좌).
        plan = plan_import_group(_gk(), [_row(), _row()], [], now=NOW)
        assert len(plan.inserts) == 1
        assert plan.intrabatch_skips == 1

    def test_no_holding_sell_excludes_group(self):
        plan = plan_import_group(_gk(), [_row(tt="SELL")], [], now=NOW)
        assert plan.excluded_reason is not None
        assert "보유 수량이 없습니다" in plan.excluded_reason
        assert len(plan.inserts) == 1  # 제외돼도 insert 분류(excluded_count 기여)

    def test_oversell_excludes_whole_group(self):
        # BUY 10 + SELL 100(빈 계좌) → oversell → 그룹 전체 제외. 두 행 모두 insert 분류.
        plan = plan_import_group(_gk(), [_row(tt="BUY", qty=10), _row(tt="SELL", qty=100, kst="2024-01-20")], [], now=NOW)
        assert plan.excluded_reason is not None
        assert "초과" in plan.excluded_reason
        assert len(plan.inserts) == 2

    def test_dup_in_excluded_group_not_counted_as_insert(self):
        # 기존 BUY 10 보유 + 파일[BUY 10(dup·noop), SELL 100(oversell)] → 제외.
        # dup BUY 는 noop → insert 아님 → excluded_count 기여(len inserts)는 SELL 1건만.
        plan = plan_import_group(
            _gk(),
            [_row(tt="BUY", qty=10), _row(tt="SELL", qty=100, kst="2024-01-20")],
            [_existing(tt="BUY", qty=10)],
            now=NOW,
        )
        assert plan.excluded_reason is not None
        assert plan.noop_skips == 1
        assert len(plan.inserts) == 1  # SELL 만(=이중차감 방지의 근거)

    def test_buy_then_sell_covered_not_excluded(self):
        plan = plan_import_group(_gk(), [_row(tt="BUY", qty=10), _row(tt="SELL", qty=5, kst="2024-01-20")], [], now=NOW)
        assert plan.excluded_reason is None
        assert len(plan.inserts) == 2

    def test_foreign_missing_rate_rejected(self):
        # 해외(US)인데 exchange_rate 1.0 → 행 거절(insert 아님). preview·commit 동일하게 거절.
        plan = plan_import_group(
            _gk(ticker="AAPL", name="Apple", country="US"),
            [_row(ticker="AAPL", name="Apple", country="US", rate=1.0)],
            [], now=NOW,
        )
        assert plan.inserts == []
        assert len(plan.rejects) == 1
        assert "환율 누락" in plan.rejects[0][1]

    def test_foreign_with_rate_inserts(self):
        plan = plan_import_group(
            _gk(ticker="AAPL", name="Apple", country="US"),
            [_row(ticker="AAPL", name="Apple", country="US", rate=1350.0, px=200.0)],
            [], now=NOW,
        )
        assert len(plan.inserts) == 1
        assert plan.rejects == []


class TestPreviewCountsMatchCommitBuckets:
    """preview 응답 카운트(_preview_counts)가 commit 버킷과 정의상 일치하는지 durable 가드.

    이 매핑이 두 번 회귀했다(초기 `if account_id` 게이트, 그다음 dup∩excluded 이중차감).
    같은 plan 집합에서 preview 카운트와 commit 버킷을 각각 구해 대조한다.
    """

    def _plans(self):
        gk = _gk()
        return [
            GroupPlan(group_key=gk, inserts=[{}, {}]),          # 정상 insert 2건
            GroupPlan(group_key=gk, merges=[(None, {})]),       # merge 1건
            GroupPlan(group_key=gk, noop_skips=2),              # 이미 등록됨(변경 없음) 2건
            # 제외 그룹: dup(noop) 1 + insert(SELL) 1 → oversell 제외.
            GroupPlan(group_key=gk, inserts=[{}], noop_skips=1, excluded_reason="oversell"),
        ]

    def test_effnew_equals_commit_inserted_and_dup_equals_merged(self):
        plans = self._plans()
        new_count, dup, excluded, unchanged = _preview_counts(plans)
        eff_new = new_count - excluded  # FE effectiveNewCount

        commit_inserted = sum(len(p.inserts) for p in plans if not p.excluded_reason)
        commit_merged = sum(len(p.merges) for p in plans if not p.excluded_reason)

        # 제외 그룹의 insert 는 new 와 excluded 양쪽에 1씩 → effNew 에서 정확히 상쇄(이중차감 없음).
        assert new_count == 3
        assert excluded == 1
        assert eff_new == commit_inserted == 2
        assert dup == commit_merged == 1
        # 이미 등록됨 = noop 전체(제외 그룹의 noop 1 포함).
        assert unchanged == 3
