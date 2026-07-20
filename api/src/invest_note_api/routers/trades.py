"""trades 라우터 — 6 endpoints + import (preview/commit)."""
from __future__ import annotations

import logging
import re
from uuid import UUID
from collections import defaultdict
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.accounts_repo import list_accounts as repo_list_accounts
from invest_note_api.db_ops.custom_tags_repo import (
    create_custom_tag,
    delete_custom_tag,
    list_custom_tags,
)
from invest_note_api.db_ops.import_ledger_repo import (
    get_ledger_trade_rows,
    mark_batch_committed,
)
from invest_note_api.db_ops.pnl_sync import recalc_group_pnl
from invest_note_api.db_ops.trades_repo import (
    IMPORT_LOCKED_FIELDS,
    PNL_AFFECTING_FIELDS,
    acquire_trade_group_lock,
    assert_account_exists,
    delete_trade,
    delete_trades_by_ids,
    get_trade_by_id,
    get_trade_with_account,
    insert_trade,
    insert_trades_bulk,
    list_trades_by_ids,
    list_trades_in_group,
    list_trades_with_account,
    patch_trade,
    strip_sell_auto_derived,
    update_trade_from_import,
)
from invest_note_api.domain.holdings import (
    compute_flexible_breakdown,
    compute_holding_summary,
)
from invest_note_api.domain.analysis.strategy_adherence import evaluate_strategy_for_sell
from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    is_same_group,
    sort_for_calc,
    trade_to_group_key,
    validate_mutation,
)
from invest_note_api.domain.trade_walker import walk_trades
from invest_note_api.domain.trade_import import parse_kst_date
from invest_note_api.domain.trade_import_plan import (
    GroupPlan,
    group_rows_by_key,
    plan_import_group,
)
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    MARKET_TYPE_STOCK,
    TRADE_TYPE_SELL,
    Trade,
)
from invest_note_api.errors import ERR_TRADE_NOT_FOUND, APIError
from invest_note_api.schemas.trade import (
    CustomTagCreate,
    TradeBulkDeleteRequest,
    TradeCreate,
    TradeUpdate,
    exchange_rate_error,
)
from invest_note_api.schemas.trade_import import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportError,
    ImportPreviewResponse,
)
from invest_note_api.schemas.trade_response import TradeSummaryResponse
from invest_note_api.broker_import import PARSERS
from invest_note_api.broker_import.ticker_resolver import resolve_tickers
from invest_note_api.config import Settings, get_settings
from invest_note_api.services.broker_capture import capture_statement

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/trades")

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-_가-힣]+$")


# account_id 미확정(신규 계좌 등록 예정) preview 의 그룹 키/시그니처용 sentinel.
# 신규 계좌는 commit 시점에 빈 상태로 생성되므로 기존 보유 없이 file-internal oversell 만 본다.
_PREVIEW_NEW_ACCOUNT = "__preview_new_account__"


async def _plan_groups(
    pool: asyncpg.Pool,
    user_id,
    account_id: str | None,
    rows: list[dict],
) -> list[GroupPlan]:
    """staging rows 를 그룹별 import 결정(GroupPlan)으로 계산한다.

    preview·commit 이 공유하는 순수 `plan_import_group`(domain.trade_import_plan)에 홀딩스를
    주입한다. account_id 가 None(신규 계좌 등록 예정)이면 기존 보유를 빈 상태로 본다 — commit 이
    방금 만든 빈 계좌에 적용하는 것과 동일해, preview 카운트와 commit 적용이 어긋나지 않는다
    (신규 계좌는 보유 0이라 매도만 있으면 오히려 oversell 이 더 잘 난다 — "보유0=불가" 는 오판).
    """
    if not rows:
        return []

    group_account = account_id or _PREVIEW_NEW_ACCOUNT
    groups = group_rows_by_key(rows, group_account)

    existing_by_group: dict[TradeGroupKey, list[Trade]] = {gk: [] for gk in groups}
    if account_id is not None:
        async with acquire_for_user(pool, user_id) as conn:
            await assert_account_exists(conn, account_id, user_id)
            for group_key in groups:
                existing_by_group[group_key] = await list_trades_in_group(
                    conn, user_id, group_key
                )

    now = datetime.now(timezone.utc)
    return [
        plan_import_group(gk, group_rows, existing_by_group[gk], now=now)
        for gk, group_rows in groups.items()
    ]


def _preview_counts(plans: list[GroupPlan]) -> tuple[int, int, int, int]:
    """plan 목록 → (new_count, duplicate_count, excluded_count, unchanged_count).

    commit 버킷과 정의상 일치: FE effectiveNewCount(=new_count - excluded_count) =
    Σinserts(비제외) = commit inserted, duplicate_count = Σmerges(비제외) = commit merged.
    제외 그룹의 insert 를 new 와 excluded 양쪽에 넣어 상쇄시키므로(제외 그룹의 dup 을 이중
    차감하던 회귀 방지) 반드시 이 함수로 센다. preview 와 commit 이 어긋나지 않는 단일 매핑.

    unchanged_count = Σnoop(전체) — 계좌에 이미 동일하게 있는(변경 없음) 행 수. "이미 등록됨"
    으로 노출해 재업로드 시 이미 있던 거래가 카운트에서 사라져 보이는 혼란을 막는다.
    """
    new_count = sum(len(p.inserts) for p in plans)
    excluded_count = sum(len(p.inserts) for p in plans if p.excluded_reason)
    duplicate_count = sum(len(p.merges) for p in plans if not p.excluded_reason)
    unchanged_count = sum(p.noop_skips for p in plans)
    return new_count, duplicate_count, excluded_count, unchanged_count


async def _validate_import_groups(
    pool: asyncpg.Pool,
    user_id,
    account_id: str | None,
    rows: list[dict],
) -> tuple[list[ImportError], int]:
    """preview 정합성 검증(oversell) — `_plan_groups` 위 얇은 래퍼.

    NOTE: 현재 import_preview 는 `_plan_groups`+`_preview_counts` 를 직접 쓴다. 이 래퍼는
    단위 테스트 편의용으로만 남아 있다(프로덕션 경로 아님).

    반환값: (validation_errors, excluded_count).
    """
    plans = await _plan_groups(pool, user_id, account_id, rows)
    errors = [
        ImportError(row_no=0, reason=p.excluded_reason)
        for p in plans
        if p.excluded_reason
    ]
    _new, _dup, excluded_count, _unchanged = _preview_counts(plans)
    return errors, excluded_count


def _trade_dict(trade) -> dict:
    return trade.model_dump(mode="json")


def _trade_with_account_dict(trade) -> dict:
    d = _trade_dict(trade)
    d["account"] = {
        "name": d.pop("account_name", None),
        "broker": d.pop("account_broker", None),
    }
    return d


@router.get("")
async def list_trades_endpoint(
    ticker: str | None = Query(default=None),
    country: str = Query(default=DEFAULT_COUNTRY),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    if ticker is not None:
        ticker = ticker[:30]
        if not _TICKER_RE.match(ticker):
            raise APIError("잘못된 ticker 형식입니다.", 400)

    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(
            conn,
            user.id,
            ticker=ticker,
            country=country if ticker else None,
        )
        accounts = await repo_list_accounts(conn, user.id)

    return {"trades": [_trade_with_account_dict(t) for t in trades], "accounts": accounts}


@router.get("/custom-tags")
async def list_custom_tags_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """사용자 정의 태그 레지스트리 목록 — 거래 폼 분석 태그 그리드에 노출."""
    async with acquire_for_user(pool, user.id) as conn:
        tags = await list_custom_tags(conn, user.id)
    return {"tags": tags}


@router.post("/custom-tags", status_code=201)
async def create_custom_tag_endpoint(
    data: CustomTagCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """레지스트리에 태그 추가(멱등). 폼 '+' 바텀시트 저장."""
    async with acquire_for_user(pool, user.id) as conn:
        return await create_custom_tag(conn, user.id, data.label)


@router.delete("/custom-tags/{tag_id}", status_code=204)
async def delete_custom_tag_endpoint(
    tag_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """레지스트리에서만 제거 — 과거 거래 라벨은 유지."""
    async with acquire_for_user(pool, user.id) as conn:
        deleted = await delete_custom_tag(conn, user.id, tag_id)
    if not deleted:
        raise APIError("태그를 찾을 수 없습니다.", 404)
    return Response(status_code=204)


@router.post("", status_code=201)
async def create_trade(
    data: TradeCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        await assert_account_exists(conn, data.account_id, user.id)

        now = datetime.now(timezone.utc)
        new_trade = Trade(
            id="__new__",
            user_id=str(user.id),
            total_amount=data.price * data.quantity,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )

        # BUY도 lock — recalc_group_pnl이 같은 그룹 SELL들을 UPDATE하므로 BUY/SELL 모두 직렬화 필요
        group_key = trade_to_group_key(new_trade)
        await acquire_trade_group_lock(conn, str(user.id), group_key)

        group_trades = await list_trades_in_group(conn, user.id, group_key)

        if data.trade_type == TRADE_TYPE_SELL:
            holding = compute_holding_summary(group_trades, group_key)
            if holding.quantity <= 0:
                raise APIError("보유하지 않은 종목입니다.", 400)
            if data.quantity > holding.quantity:
                raise APIError(f"보유 수량이 부족합니다 (현재 {holding.quantity}주).", 400)

            ok, msg, _ = validate_mutation(group_trades, "insert", new_trade)
            if not ok:
                raise APIError(msg, 400)

        row = await insert_trade(conn, user.id, {
            "account_id": data.account_id,
            "asset_name": data.asset_name,
            "ticker_symbol": data.ticker_symbol,
            "market_type": data.market_type,
            "trade_type": data.trade_type,
            "price": data.price,
            "quantity": data.quantity,
            "traded_at": data.traded_at,
            "commission": data.commission,
            "tax": data.tax,
            "country_code": data.country_code or DEFAULT_COUNTRY,
            "exchange": data.exchange or "",
            "exchange_rate": data.exchange_rate,
        })

        fresh_trades = [*group_trades, new_trade.model_copy(update={"id": row["id"]})]
        await recalc_group_pnl(conn, fresh_trades, group_key, user.id)

    return row


@router.get(
    "/{trade_id}/summary",
    response_model=TradeSummaryResponse,
    response_model_exclude_none=True,
)
async def get_trade_summary(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> TradeSummaryResponse:
    async with acquire_for_user(pool, user.id) as conn:
        sell = await get_trade_by_id(conn, trade_id, user.id)
        if sell is None:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)
        if sell.trade_type != TRADE_TYPE_SELL:
            raise APIError("매도 거래만 조회할 수 있습니다.", 400)
        group_key = trade_to_group_key(sell)
        group_trades = await list_trades_in_group(conn, user.id, group_key)

    breakdown = compute_flexible_breakdown(sell)
    evaluation = evaluate_strategy_for_sell(sell, None)
    buy_reason = _latest_consumed_buy_reason(group_trades, sell.id)

    return TradeSummaryResponse.model_validate({
        "pnl": breakdown.pnl,
        "result": sell.result,
        "holding_days": sell.holding_days,
        "strategy_evaluation": evaluation,
        "breakdown": breakdown,
        "buy_reason": buy_reason,
    })


def _latest_consumed_buy_reason(group_trades: list[Trade], sell_id: str) -> str | None:
    """SELL이 FIFO로 소비한 BUY들 중 가장 최근(traded_at, 입력 순서) 항목의 buy_reason."""
    for event in walk_trades(
        group_trades,
        group_filter=lambda _t: True,
        sort_fn=sort_for_calc,
    ):
        if event.kind != "SELL" or event.trade.id != sell_id:
            continue
        if not event.consumed:
            return None
        latest = max(event.consumed, key=lambda c: (c.lot.time_ms, c.lot.order))
        reason = (latest.lot.source_trade.buy_reason or "").strip()
        return reason or None
    return None


@router.get("/{trade_id}")
async def get_trade(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        trade = await get_trade_with_account(conn, trade_id, user.id)

    if trade is None:
        raise APIError("거래를 찾을 수 없습니다.", 404)
    return _trade_with_account_dict(trade)


@router.patch("/{trade_id}", responses={204: {"description": "No fields to update"}})
async def update_trade(
    trade_id: str,
    data: TradeUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    fields = data.model_fields_set
    if not fields:
        return Response(status_code=204)

    patch = data.model_dump(exclude_unset=True)

    async with acquire_for_user(pool, user.id) as conn:
        existing = await get_trade_by_id(conn, trade_id, user.id)
        if existing is None:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        # 거래내역서(import) 거래의 금액(사실) 필드는 불변 — 잠금 5필드 patch 시도 거부.
        # 메타(전략/감정/태그/메모)는 그대로 허용해 사용자 저널링 여지를 남긴다.
        if existing.origin == "IMPORT" and fields & IMPORT_LOCKED_FIELDS:
            raise APIError("거래내역서에서 가져온 거래는 금액 정보를 수정할 수 없어요.", 422)

        patch, fields = strip_sell_auto_derived(patch, fields, existing.trade_type)
        if not patch:
            return Response(status_code=204)

        # TradeUpdate 에는 country_code 가 없어 스키마 validator 로 검증 불가.
        # existing.country_code 기준으로 create 와 대칭 가드(exchange_rate_error 공유).
        # patch 에 exchange_rate 미포함이면 .get→None 이라 자동 skip(기존 환율 유지).
        patch_rate = patch.get("exchange_rate")
        if patch_rate is not None:
            rate_err = exchange_rate_error(existing.country_code, patch_rate)
            if rate_err:
                raise APIError(rate_err, 400)

        if fields & PNL_AFFECTING_FIELDS:
            key = trade_to_group_key(existing)
            await acquire_trade_group_lock(conn, str(user.id), key)
            group_trades = await list_trades_in_group(conn, user.id, key)
            ok, msg, _ = validate_mutation(group_trades, "update", existing, patch)
            if not ok:
                raise APIError(msg, 400)

            await patch_trade(conn, trade_id, user.id, patch)

            fresh_trades = [
                t.model_copy(update=patch) if t.id == trade_id else t
                for t in group_trades
            ]
            await recalc_group_pnl(conn, fresh_trades, key, user.id)
        else:
            # 파생 SELL 값에 영향을 주지 않는 메타 필드는 lock/recalc 없이 수정.
            # PNL_AFFECTING_FIELDS에 없는 필드 추가 시 이 분기를 재검토할 것.
            await patch_trade(conn, trade_id, user.id, patch)

    return Response(status_code=204)


@router.delete("/{trade_id}", status_code=204)
async def delete_trade_endpoint(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with acquire_for_user(pool, user.id) as conn:
        target = await get_trade_by_id(conn, trade_id, user.id)
        if target is None:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        key = trade_to_group_key(target)
        await acquire_trade_group_lock(conn, str(user.id), key)

        group_trades = await list_trades_in_group(conn, user.id, key)
        ok, _, _ = validate_mutation(group_trades, "delete", target)
        if not ok:
            # validate_mutation 의 메시지는 "매도 시점" 관점이라 삭제 컨텍스트에서 오인을 일으킨다.
            raise APIError(
                "매도 거래에 매칭되어 있어 삭제할 수 없습니다. 매도 거래를 먼저 삭제해 주세요.",
                400,
            )

        await delete_trade(conn, trade_id, user.id)

        remaining = [t for t in group_trades if t.id != trade_id]
        await recalc_group_pnl(conn, remaining, key, user.id)

    return Response(status_code=204)


def _find_bulk_delete_oversell(
    remaining_trades: list[Trade],
    key: TradeGroupKey,
    account_name: str,
) -> str | None:
    """가상 제거 후 trades 에 oversell/no_holding SELL 이 있으면 사용자용 사유 문자열 반환.

    `validate_mutation` 은 단일 mutation 만 검증하므로, 다건 가상 삭제는 walk_trades 로 직접 순회한다.
    `trade_import_plan.find_import_oversell` 와 동일 패턴이지만 메시지 prefix 가 계좌명을 포함하고 import 의 안내
    문구가 빠진다 — 라우터에서 그룹 단위 메시지를 모아 한 번에 안내한다.
    """
    for ev in walk_trades(
        remaining_trades,
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
                f"{account_name} · {asset} {traded_date} "
                "매도 거래에 해당하는 보유 수량이 없습니다"
            )
        if ev.oversell:
            return (
                f"{account_name} · {asset} {traded_date} "
                "매도 수량이 보유 수량을 초과합니다"
            )
    return None


@router.post("/bulk-delete", status_code=204)
async def bulk_delete_trades(
    body: TradeBulkDeleteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """다중 거래 일괄 삭제 — 단일 트랜잭션, 전부 성공 or 전부 롤백.

    1. 모든 id 조회 → 누락이면 404 (DELETE 실행 없음).
    2. 영향 그룹 키 수집 → **결정적 정렬 순서**(account_id, country, ticker or "", asset_name)
       로 acquire_trade_group_lock — 동시 요청 데드락 회피.
    3. 그룹별 list_trades_in_group → 가상 제거 → walk_trades 로 oversell 검증.
       충돌이 하나라도 있으면 400 raise → 트랜잭션 롤백 (DELETE 실행 전).
    4. 통과 시 그룹별로 delete_trade 일괄 + recalc_group_pnl 1회.
    """
    # 같은 id 가 두 번 들어와도 단건만 처리되도록 dedup (입력 순서 유지).
    unique_ids = list(dict.fromkeys(body.ids))

    async with acquire_for_user(pool, user.id) as conn:
        # 1) 모든 id 를 단일 쿼리로 조회 (N+1 회피).
        # malformed UUID 는 asyncpg 가 DataError(InvalidTextRepresentationError 포함) 를,
        # 클라이언트 인코딩 실패는 ValueError 를 던지므로 사용자용 422 로 변환한다
        # (그대로 두면 핸들링 안 된 500 으로 새어 나감).
        try:
            targets = await list_trades_by_ids(conn, unique_ids, user.id)
        except (asyncpg.exceptions.DataError, ValueError):
            raise APIError("거래 ID 형식이 올바르지 않습니다.", 422)
        # 누락이 하나라도 있으면 즉시 404, 이후 단계 진입 없음.
        if len(targets) != len(unique_ids):
            raise APIError("일부 거래를 찾을 수 없습니다.", 404)

        # 2) 영향 그룹 키 수집 + 그룹 → 삭제 대상 id 매핑.
        delete_ids_by_group: dict[TradeGroupKey, set[str]] = defaultdict(set)
        for t in targets:
            delete_ids_by_group[trade_to_group_key(t)].add(t.id)

        # 메시지 prefix 용 account_id → name 맵 (1회 fetch).
        accounts = await repo_list_accounts(conn, user.id)
        account_name_by_id: dict[str, str] = {
            str(a["id"]): a.get("name") or "" for a in accounts
        }

        # 데드락 회피: (account_id, country, ticker or "", asset_name) 결정적 정렬 순서로 lock 획득.
        sorted_keys = sorted(
            delete_ids_by_group.keys(),
            key=lambda k: (k.account_id, k.country, k.ticker or "", k.asset_name),
        )

        # 3) 그룹별 락 → list → 가상 제거 → 검증. 충돌 메시지 누적.
        group_remaining: dict[TradeGroupKey, list[Trade]] = {}
        conflict_msgs: list[str] = []
        for key in sorted_keys:
            await acquire_trade_group_lock(conn, str(user.id), key)
            group_trades = await list_trades_in_group(conn, user.id, key)
            delete_ids = delete_ids_by_group[key]
            remaining = [t for t in group_trades if t.id not in delete_ids]
            group_remaining[key] = remaining

            account_name = account_name_by_id.get(key.account_id, "")
            msg = _find_bulk_delete_oversell(remaining, key, account_name)
            if msg is not None:
                conflict_msgs.append(msg)

        if conflict_msgs:
            # 최대 3 그룹 노출, 그 이상은 "외 N건" 축약.
            head = conflict_msgs[:3]
            joined = "; ".join(head)
            if len(conflict_msgs) > 3:
                joined += f" 외 {len(conflict_msgs) - 3}건"
            raise APIError(f"{joined}. 일부 거래를 삭제하지 못했습니다.", 400)

        # 4) 검증 통과 → 실제 DELETE (전체 id 단일 쿼리) + 그룹별 recalc.
        # recalc 는 in-memory group_remaining 를 입력으로 쓰므로 delete 와 순서 무관.
        await delete_trades_by_ids(conn, unique_ids, user.id)
        for key in sorted_keys:
            await recalc_group_pnl(conn, group_remaining[key], key, user.id)

    return Response(status_code=204)


# ── Import endpoints ──────────────────────────────────────────────────────────


def _coerce_uuid(value: str) -> UUID | None:
    """batch_id(클라이언트 제공 문자열)를 UUID 로. 형식 오류면 None(→ 미존재 취급)."""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def _num_or(value: object, default: float) -> float:
    """numeric(Decimal)→float. None 이면 default. (기존 staging 경로와 동일한 float 타입 유지)"""
    return float(value) if value is not None else default


def _rows_from_ledger(
    ledger_rows: list, ticker_map: dict
) -> tuple[list[dict], list[ImportError]]:
    """원장 거래 행(Record) + 해소 결과 → commit 이 소비하는 row dict 리스트.

    staging 이 저장하던 dict 와 동형(ticker_symbol/exchange 는 재해소 산출). 미해결 행은
    commit_error 로 분리한다. 금액값은 numeric→float(기존 staging 경로와 동일한 타입).
    """
    rows: list[dict] = []
    errors: list[ImportError] = []
    for lr in ledger_rows:
        country = lr["country_code"] or DEFAULT_COUNTRY
        asset = lr["asset_name"]
        resolved = ticker_map.get((country, asset))
        if resolved is None:
            errors.append(
                ImportError(
                    row_no=lr["source_row_no"],
                    reason=f"ticker 미해결: {asset} — 종목명에서 코드를 찾지 못함",
                )
            )
            continue
        # 날짜 유효성(미래·파싱불가)은 캡처 시점에 파일 단위로 이미 거절됨 → 원장 행은 유효 날짜.
        raw_kst = lr["traded_at_raw"] or ""
        rows.append(
            {
                "asset_name": asset,
                "ticker_symbol": resolved["code"],
                "market_type": MARKET_TYPE_STOCK,
                "trade_type": lr["trade_type"],
                "price": _num_or(lr["price"], 0.0),
                "quantity": _num_or(lr["quantity"], 0.0),
                "traded_at_kst": raw_kst[:10],
                "traded_at_kst_full": raw_kst if len(raw_kst) > 10 else None,
                "commission": _num_or(lr["commission"], 0.0),
                "tax": _num_or(lr["tax"], 0.0),
                "country_code": country,
                "exchange_rate": _num_or(lr["exchange_rate"], 1.0),
                "exchange": resolved["exchange"],
                "source_ledger_entry_id": lr["id"],
            }
        )
    return rows, errors


@router.post("/import/preview")
async def import_preview(
    file: UploadFile = File(...),
    broker_key: str | None = None,
    account_id: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    settings: Settings = Depends(get_settings),
) -> ImportPreviewResponse:
    """파일을 파싱해 중복 체크 후 staging cache에 저장한다. commit 전에 호출."""
    filename = file.filename or ""
    file_bytes = await file.read()

    _MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise APIError("파일 크기가 너무 큽니다 (최대 20 MB).", 413)

    allowed_extensions = {".xlsx", ".xls", ".pdf"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise APIError("지원하지 않는 파일 형식입니다 (xlsx, xls, pdf만 허용).", 415)

    if not broker_key or broker_key not in PARSERS:
        raise APIError("지원하지 않는 증권사입니다. broker_key를 확인해주세요.", 400)

    parser = PARSERS[broker_key]
    # Stage 1 캡처(파싱 threadpool + 미스매치 가드 + 원본 R2 + 원장 적재)를 서비스에 위임한다.
    # 파싱/미스매치 400 안내는 capture_statement 가 담당. 반환 batch_id 를 preview→commit
    # 사이의 핸들(응답 staging_id 필드)로 쓴다 — 원장이 durable 이라 TTL staging 이 불필요.
    capture = await capture_statement(
        pool,
        settings,
        user_id=user.id,
        broker_key=broker_key,
        filename=filename,
        content_type=file.content_type,
        file_bytes=file_bytes,
    )
    parse_result = capture.parse_result

    now_utc = datetime.now(timezone.utc)

    # ticker 해결 (로컬 stocks 마스터 조회 — public 테이블이라 plain connection)
    # (country_code, asset_name) 키로 country-scoped 매칭 — US 종목명이 KR alias 에
    # 오매칭(예: 애플→PLUS 애플채권혼합)되는 것을 막는다.
    resolve_items = {(t.country_code, t.asset_name) for t in parse_result.trades}
    ticker_hints = {
        (t.country_code, t.asset_name): t.ticker_hint
        for t in parse_result.trades
        if t.ticker_hint
    }
    # ISIN(토스 해외 USD 행) 은 ticker_hint 와 분리 — OpenFIGI 로 해소(ISIN 매칭 우선).
    isins = {
        (t.country_code, t.asset_name): t.isin
        for t in parse_result.trades
        if t.isin
    }

    async with pool.acquire() as conn:
        ticker_map = await resolve_tickers(
            resolve_items,
            ticker_hints,
            conn=conn,
            isins=isins,
            openfigi_api_key=settings.openfigi_api_key or None,
        )

    rows_to_stage: list[dict] = []
    unresolved_ticker_count = 0
    parse_errors: list[ImportError] = [
        ImportError(row_no=e["row_no"], reason=e["reason"])
        for e in parse_result.errors
    ]

    for pt in parse_result.trades:
        resolved = ticker_map.get((pt.country_code, pt.asset_name))
        if resolved is None:
            unresolved_ticker_count += 1
            parse_errors.append(ImportError(
                row_no=pt.source_row_no,
                reason=f"ticker 미해결: {pt.asset_name} — 종목명에서 코드를 찾지 못함",
            ))
            continue
        ticker = resolved["code"]

        # traded_at 파싱 (KST → UTC)
        traded_date = parse_kst_date(pt.traded_at_kst)
        if traded_date is None:
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason=f"날짜 파싱 오류: {pt.traded_at_kst}"))
            continue
        kst_str = pt.traded_at_kst[:10]  # "YYYY-MM-DD" — commit 경로에서 재사용
        # 시각 정보가 함께 들어온 경우만 보관 (머지 시 traded_at 정밀도 갱신용)
        kst_full = pt.traded_at_kst if len(pt.traded_at_kst) > 10 else None

        if traded_date > now_utc.date():
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason="미래 일자 거래 등록 불가"))
            continue

        rows_to_stage.append({
            "asset_name": pt.asset_name,
            "ticker_symbol": ticker,
            "market_type": MARKET_TYPE_STOCK,
            "trade_type": pt.trade_type,
            "price": pt.price,
            "quantity": pt.quantity,
            "traded_at_kst": kst_str,  # commit 시 KST→UTC 변환
            "traded_at_kst_full": kst_full,  # 시각 정보 있을 때만 (머지 traded_at 갱신용)
            "commission": pt.commission,
            "tax": pt.tax,
            "country_code": pt.country_code,
            "exchange_rate": pt.exchange_rate,
            "exchange": resolved["exchange"],
        })

    # staged 중 해외(country_code != KR) 행 수. resolved(ticker 매칭된) 행만 집계되므로
    # ISIN 미해결 USD 종목은 포함되지 않는다 — FE 의 "해외 N건 포함" 안내 분기에 사용.
    foreign_count = sum(1 for r in rows_to_stage if r["country_code"] != DEFAULT_COUNTRY)

    # 원장이 이미 durable 캡처했으므로 별도 staging 저장이 없다. commit 은 batch_id 로
    # 원장을 다시 읽는다(재해소는 캐시). staging_id 필드에 batch_id 를 실어 FE 계약을 유지한다.
    staging_id = capture.batch_id

    # preview 카운트와 commit 적용은 동일한 plan(domain.trade_import_plan)에서 파생한다 —
    # 그룹핑·시그니처 분류·oversell·행거절을 한 곳에서 계산해 preview≠commit 드리프트를 없앤다.
    # account_id 없으면(신규 계좌 예정) 빈 보유로 본다(commit 이 빈 계좌 생성 후 적용과 동일).
    plans = await _plan_groups(pool, user.id, account_id, rows_to_stage)
    for p in plans:
        for _row, reason in p.rejects:
            parse_errors.append(ImportError(row_no=0, reason=reason))
    validation_errors = [
        ImportError(row_no=0, reason=p.excluded_reason) for p in plans if p.excluded_reason
    ]
    new_count, duplicate_count, excluded_count, unchanged_count = _preview_counts(plans)

    return ImportPreviewResponse(
        staging_id=staging_id,
        broker_key=broker_key,
        broker_name=parser.display_name,
        account_hint=parse_result.account_hint,
        new_count=new_count,
        duplicate_count=duplicate_count,
        error_count=len(parse_errors),
        usd_skip_count=parse_result.usd_skip_count,
        foreign_count=foreign_count,
        unresolved_ticker_count=unresolved_ticker_count,
        errors=parse_errors,
        validation_errors=validation_errors,
        excluded_count=excluded_count,
        unchanged_count=unchanged_count,
    )


@router.post("/import/commit")
async def import_commit(
    body: ImportCommitRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    settings: Settings = Depends(get_settings),
) -> ImportCommitResponse:
    """원장(batch_id=staging_id)의 거래 행을 재해소해 trades 로 물질화(INSERT/merge)한다."""
    commit_errors: list[ImportError] = []
    inserted_count = 0
    merged_count = 0
    skipped_count = 0

    batch_uuid = _coerce_uuid(body.staging_id)
    if batch_uuid is None:
        raise APIError("잘못된 요청입니다. 파일을 다시 업로드해주세요.", 400)

    # 1) 원장 읽기 + ticker 재해소 (write 트랜잭션 밖 — preview 와 동일 패턴, 대개 캐시 히트).
    async with pool.acquire() as conn:
        ledger_rows = await get_ledger_trade_rows(
            conn, batch_id=batch_uuid, user_id=user.id
        )
        if not ledger_rows:
            raise APIError("등록할 거래를 찾지 못했습니다. 파일을 다시 업로드해주세요.", 400)
        resolve_items = {(r["country_code"], r["asset_name"]) for r in ledger_rows}
        ticker_hints = {
            (r["country_code"], r["asset_name"]): r["ticker_hint"]
            for r in ledger_rows
            if r["ticker_hint"]
        }
        isins = {
            (r["country_code"], r["asset_name"]): r["isin"]
            for r in ledger_rows
            if r["isin"]
        }
        ticker_map = await resolve_tickers(
            resolve_items,
            ticker_hints,
            conn=conn,
            isins=isins,
            openfigi_api_key=settings.openfigi_api_key or None,
        )

    rows, resolve_errors = _rows_from_ledger(ledger_rows, ticker_map)
    commit_errors.extend(resolve_errors)

    # 2) group/merge/insert (write 트랜잭션) — 소스만 원장으로 바뀌고 dedup/merge 로직은 동일.
    async with acquire_for_user(pool, user.id) as conn:
        await assert_account_exists(conn, body.account_id, user.id)

        # 원장 rows를 (account_id, ticker, country) 그룹으로 분할 후 그룹별로 처리
        groups: dict[TradeGroupKey, list[dict]] = defaultdict(list)
        for row in rows:
            group_key = TradeGroupKey(
                account_id=str(body.account_id),
                ticker=row["ticker_symbol"],
                asset_name=row["asset_name"],
                country=row["country_code"],
            )
            groups[group_key].append(row)

        for group_key, group_rows in groups.items():
            # except 핸들러가 항상 참조할 수 있게 미리 초기화(조회/결정 단계 예외 대비).
            err_asset = group_key.asset_name
            # skip 은 그룹 트랜잭션이 커밋될 때만 전역 집계에 반영한다(INSERT raise→롤백 시
            # 파이썬 증가분이 살아남아 과대 보고되는 것 방지).
            group_skipped = 0
            try:
                async with conn.transaction():
                    # advisory lock 을 기존 거래 조회보다 *먼저* 획득한다. 같은 batch 를 동시
                    # 재커밋(더블클릭·재시도·두 탭)하면 두 요청이 lock 전에 빈 그룹을 읽어 양쪽 다
                    # INSERT 하는 TOCTOU 중복이 발생한다 → lock 선점 시 뒤 요청이 앞 요청의 커밋분을
                    # 읽어 dedup(부분 UNIQUE 인덱스가 최후 방어). 조회·결정·적용을 lock 안에서 수행.
                    await acquire_trade_group_lock(conn, str(user.id), group_key)

                    # 그룹별 기존 거래 페치(lock 안 = 직렬화된 최신 상태) → preview 와 공유하는
                    # 순수 plan 으로 insert/merge/skip/reject/제외를 결정한다(드리프트 방지).
                    group_existing = await list_trades_in_group(conn, user.id, group_key)
                    now_for_virtual = datetime.now(timezone.utc)
                    plan = plan_import_group(
                        group_key, group_rows, group_existing, now=now_for_virtual
                    )
                    group_skipped = plan.skips  # noop + intrabatch(제외 그룹도 skip 은 집계)

                    # 행 단위 거절(해외 환율 누락).
                    for _row, reason in plan.rejects:
                        commit_errors.append(ImportError(row_no=0, reason=reason))

                    if plan.excluded_reason is not None:
                        commit_errors.append(ImportError(row_no=0, reason=plan.excluded_reason))
                        skipped_count += group_skipped
                        continue
                    if not plan.inserts and not plan.merges:
                        # 전부 dup/noop/거절 — 빈 커밋이므로 skip 확정.
                        skipped_count += group_skipped
                        continue

                    err_asset = (
                        plan.inserts[0]["asset_name"]
                        if plan.inserts
                        else (plan.merges[0][0].asset_name if plan.merges else group_key.asset_name)
                    )

                    # 1) 머지: 기존 거래 update
                    merged_trades: list[Trade] = []
                    for existing, patch in plan.merges:
                        await update_trade_from_import(
                            conn, str(existing.id), str(user.id), patch
                        )
                        merged_trades.append(existing.model_copy(update=patch))

                    # 2) 신규 INSERT — plan.inserts(원본 row + traded_at_utc) → DB insert row.
                    insert_rows = [
                        {
                            "account_id": str(body.account_id),
                            "asset_name": r["asset_name"],
                            "ticker_symbol": r["ticker_symbol"],
                            "market_type": r["market_type"],
                            "trade_type": r["trade_type"],
                            "price": r["price"],
                            "quantity": r["quantity"],
                            "traded_at": r["traded_at_utc"],
                            "commission": r["commission"],
                            "tax": r["tax"],
                            "country_code": r["country_code"],
                            "exchange_rate": r.get("exchange_rate", 1.0),
                            "exchange": r["exchange"],
                            "origin": "IMPORT",
                            "source_ledger_entry_id": r["source_ledger_entry_id"],
                        }
                        for r in plan.inserts
                    ]
                    inserted_trades = (
                        await insert_trades_bulk(conn, str(user.id), insert_rows)
                        if insert_rows
                        else []
                    )

                    # 3) recalc 입력: 머지된 거래는 갱신값으로, 머지 안된 기존은 그대로
                    merged_ids = {m.id for m in merged_trades}
                    fresh_trades = (
                        merged_trades
                        + [t for t in group_existing if t.id not in merged_ids]
                        + list(inserted_trades)
                    )
                    await recalc_group_pnl(conn, fresh_trades, group_key, user.id)

                    inserted_count += len(inserted_trades)
                    merged_count += len(merged_trades)
                    skipped_count += group_skipped
            except asyncpg.LockNotAvailableError:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 처리 중 충돌 — 잠시 후 다시 시도해주세요."))
            except asyncpg.UniqueViolationError:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 중복 거래 감지 — 이미 등록된 거래가 있습니다."))
            except asyncpg.PostgresError as e:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} DB 오류 ({e.sqlstate}): {e.args[0] if e.args else e}"))
            except Exception:
                logger.exception("import commit 처리 오류 user_id=%s asset=%s", user.id, err_asset)
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 처리 오류 — 잠시 후 다시 시도해주세요."))

        # 원장은 durable 하므로 삭제하지 않는다. transient 실패가 섞였으면 사용자가 같은
        # batch_id 로 commit 재시도(재업로드·재해소 없이) — trade-signature dedup 이 멱등 보장.
        # 등록 생애주기 마커 — 미리보기만 한 배치와 구분(committed_at·account_id 채움).
        # 단, 전 그룹이 실패해 아무것도 물질화되지 않았고 오류만 남았으면 스탬프하지 않는다
        # (어드민 원장에 '등록됨'으로 오표시되는 것 방지). 전부 dup/noop(오류 0)은 정상
        # 재커밋이므로 마커를 남긴다.
        if inserted_count or merged_count or not commit_errors:
            await mark_batch_committed(
                conn, batch_id=batch_uuid, user_id=user.id, account_id=body.account_id
            )

    return ImportCommitResponse(
        inserted_count=inserted_count,
        merged_count=merged_count,
        skipped_count=skipped_count,
        error_count=len(commit_errors),
        errors=commit_errors,
    )
