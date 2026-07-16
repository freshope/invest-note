"""일괄등록 판단(plan) — preview 카운트와 commit 적용이 공유하는 순수 결정 로직.

preview 와 commit 이 각자 그룹핑·시그니처 분류·oversell 판정을 중복 구현하던 것을 이 한
곳으로 모은다(드리프트 방지 — 한쪽만 고쳐 preview≠commit 이 되던 버그 클래스 제거). 이
모듈은 순수하다(DB·lock 무관): 그룹의 거래 행 dict 리스트와 그 그룹의 기존 보유 거래(빈
리스트면 신규/빈 계좌)를 받아 insert/merge/skip/reject/그룹제외 결정을 반환한다. lock·
트랜잭션·recalc·실 INSERT 는 호출자(commit)의 몫이다(적용 관심사).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from .realized_pnl import TradeGroupKey, is_same_group, sort_for_calc
from .trade_import import build_merge_patch, make_signature, trade_to_signature
from .trade_types import (
    CURRENCY_KRW,
    MARKET_TYPE_STOCK,
    TRADE_TYPE_BUY,
    Trade,
    currency_for_country,
)
from .trade_utils import kst_date_to_utc
from .trade_walker import walk_trades


def find_import_oversell(trades: list[Trade], key: TradeGroupKey) -> str | None:
    """fresh_trades 에 oversell/no_holding SELL 이 있으면 사용자용 사유 문자열 반환.

    수동 등록은 `validate_mutation` 한 mutation씩 검증하지만, 일괄 등록은 같은 그룹에
    여러 INSERT/UPDATE 가 동시 적용되므로 walk_trades 로 직접 순회한다.
    """
    for ev in walk_trades(
        trades,
        group_filter=lambda t: is_same_group(t, key),
        sort_fn=sort_for_calc,
        track_fifo_lots=False,
    ):
        if ev.kind != "SELL":
            continue
        asset = ev.trade.asset_name or key.asset_name
        traded_date = ev.trade.traded_at.date().isoformat()
        if ev.no_holding:
            return (
                f"{asset} {traded_date} 매도 거래에 해당하는 보유 수량이 없습니다. "
                "이 종목 거래는 제외되고 나머지 거래만 등록됩니다."
            )
        if ev.oversell:
            return (
                f"{asset} {traded_date} 매도 수량이 보유 수량을 초과합니다. "
                "이 종목의 매수 거래까지 함께 제외되고 다른 종목 거래만 등록됩니다."
            )
    return None


@dataclass
class GroupPlan:
    """한 그룹(계좌·종목·국가)의 import 결정.

    inserts/merges 는 그룹이 제외(excluded_reason)되면 적용되지 않는다. skips/rejects 는
    적용 여부와 무관하게 발생한 사실이다.
    """

    group_key: TradeGroupKey
    # insert 대상 원본 row dict + "traded_at_utc"(datetime) 부가 — commit apply 가 바로 씀.
    inserts: list[dict] = field(default_factory=list)
    merges: list[tuple[Trade, dict]] = field(default_factory=list)  # (existing, patch)
    noop_skips: int = 0            # 기존 거래와 완전 동일(패치 없음) → 변경 없음
    intrabatch_skips: int = 0      # 같은 batch 내 동일 시그니처 재등장 → skip
    rejects: list[tuple[dict, str]] = field(default_factory=list)   # 행 단위 거절(row, reason)
    excluded_reason: str | None = None  # oversell/무보유 → 그룹 전체 미적용

    @property
    def skips(self) -> int:
        """commit skipped_count 기여 — noop + intrabatch(제외 그룹도 skip 은 집계)."""
        return self.noop_skips + self.intrabatch_skips

    @property
    def matched_existing(self) -> int:
        """dup_count 기여 — 기존 계좌 거래와 매칭된 행(merge + noop)."""
        return len(self.merges) + self.noop_skips


def group_rows_by_key(
    rows: list[dict], account_id: str
) -> dict[TradeGroupKey, list[dict]]:
    """import row dict 를 (account_id, ticker, asset_name, country) 그룹으로 분할."""
    groups: dict[TradeGroupKey, list[dict]] = defaultdict(list)
    for row in rows:
        key = TradeGroupKey(
            account_id=account_id,
            ticker=row["ticker_symbol"],
            asset_name=row["asset_name"],
            country=row["country_code"],
        )
        groups[key].append(row)
    return groups


def plan_import_group(
    group_key: TradeGroupKey,
    group_rows: list[dict],
    existing_trades: list[Trade],
    *,
    now: datetime,
) -> GroupPlan:
    """그룹 1개의 import 결정을 계산한다(순수). preview·commit 이 공유.

    BUY→SELL 순으로 정렬 후 시그니처로 분류(기존매칭→merge/noop, batch내중복→skip,
    해외환율누락→reject, 그 외→insert)하고, 가상 적용(virtual_fresh)에 oversell 이 있으면
    그룹 전체를 제외 표시한다. `now` 는 oversell walk 용 가상 Trade timestamp(정렬 무영향).
    """
    plan = GroupPlan(group_key=group_key)
    account_id = group_key.account_id
    existing_by_sig: dict = {
        trade_to_signature(t, account_id): t for t in existing_trades
    }
    seen_sigs: set = set(existing_by_sig.keys())

    sorted_rows = sorted(
        group_rows,
        key=lambda r: (r["traded_at_kst"], 0 if r["trade_type"] == TRADE_TYPE_BUY else 1),
    )

    virtual_inserts: list[Trade] = []
    virtual_merged: list[Trade] = []
    for i, row in enumerate(sorted_rows):
        traded_date = date.fromisoformat(row["traded_at_kst"])
        kst_full = row.get("traded_at_kst_full")
        if kst_full:
            kst_dt = datetime.fromisoformat(kst_full)
            traded_at_utc = kst_date_to_utc(kst_dt.date(), kst_dt.time())
            row_for_merge = {**row, "traded_at_utc": traded_at_utc}
        else:
            traded_at_utc = kst_date_to_utc(traded_date)
            row_for_merge = row

        sig = make_signature(
            account_id=account_id,
            trade_date=traded_date,
            ticker=row["ticker_symbol"],
            asset_name=row["asset_name"],
            trade_type=row["trade_type"],
            quantity=row["quantity"],
            price=row["price"],
        )
        existing = existing_by_sig.get(sig)
        if existing is not None:
            patch = build_merge_patch(existing, row_for_merge)
            if patch:
                plan.merges.append((existing, patch))
                virtual_merged.append(existing.model_copy(update=patch))
            else:
                plan.noop_skips += 1
            continue
        if sig in seen_sigs:
            plan.intrabatch_skips += 1
            continue

        # 해외 환율 가드(행 단위 거절): 해외(비-KRW)인데 exchange_rate 가 1.0/누락이면 native
        # 금액이 KRW 로 오인 집계(원가 ~환율배 부풀림)되므로 그 행만 거절한다(침묵 통과 금지).
        if (
            currency_for_country(row["country_code"]) != CURRENCY_KRW
            and row.get("exchange_rate", 1.0) == 1.0
        ):
            plan.rejects.append((
                row,
                f"{row['asset_name']} 해외 거래 환율 누락 — exchange_rate 가 필요합니다.",
            ))
            continue

        seen_sigs.add(sig)
        plan.inserts.append({**row, "traded_at_utc": traded_at_utc})
        virtual_inserts.append(Trade(
            id=f"__pending_{i}",
            user_id="__plan__",  # oversell walk 는 user_id 미사용
            account_id=account_id,
            asset_name=row["asset_name"],
            ticker_symbol=row["ticker_symbol"],
            market_type=row.get("market_type", MARKET_TYPE_STOCK),
            trade_type=row["trade_type"],
            price=row["price"],
            quantity=row["quantity"],
            total_amount=row["price"] * row["quantity"],
            traded_at=traded_at_utc,
            commission=row["commission"],
            tax=row["tax"],
            country_code=row["country_code"],
            exchange=row.get("exchange", ""),
            created_at=now,
            updated_at=now,
        ))

    # 적용할 게 있을 때만 oversell 판정(전부 skip/noop 인 그룹은 제외가 아니라 skip).
    if plan.inserts or plan.merges:
        virtual_merged_ids = {m.id for m in virtual_merged}
        virtual_fresh = (
            virtual_merged
            + [t for t in existing_trades if t.id not in virtual_merged_ids]
            + virtual_inserts
        )
        plan.excluded_reason = find_import_oversell(virtual_fresh, group_key)

    return plan
