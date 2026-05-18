"""trades 라우터 — 6 endpoints + import (preview/commit)."""
from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import asyncpg
import cachetools
import httpx
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.accounts_repo import list_accounts as repo_list_accounts
from invest_note_api.external.http_client import get_http_client
from invest_note_api.db_ops.pnl_sync import recalc_group_pnl
from invest_note_api.db_ops.trades_repo import (
    PNL_AFFECTING_FIELDS,
    acquire_trade_group_lock,
    assert_account_exists,
    delete_trade,
    get_trade_by_id,
    get_trade_with_account,
    insert_trade,
    insert_trades_bulk,
    list_trades,
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
from invest_note_api.domain.trade_utils import kst_date_to_utc
from invest_note_api.domain.trade_import import (
    build_merge_patch,
    make_preview_signature,
    make_signature,
    parse_kst_date,
    trade_to_preview_signature,
    trade_to_signature,
)
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    MARKET_TYPE_STOCK,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    Trade,
)
from invest_note_api.errors import ERR_TRADE_NOT_FOUND, APIError
from invest_note_api.schemas.trade import TradeCreate, TradeUpdate
from invest_note_api.schemas.trade_import import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportError,
    ImportPreviewResponse,
)
from invest_note_api.schemas.trade_response import TradeSummaryResponse
from invest_note_api.broker_import import PARSERS, detect_broker
from invest_note_api.broker_import.ticker_resolver import resolve_tickers

logger = logging.getLogger(__name__)


@dataclass
class TradeStagingState:
    """import preview → commit 사이의 staging cache.

    값 형식: {staging_id: {"user_id": str, "rows": list[dict], "parse_errors": list[dict], ...}}
    `app.state.trade_staging` 에 보관하고 라우터에서 `Depends(get_trade_staging_state)` 로 주입.
    """

    cache: cachetools.TTLCache = field(
        default_factory=lambda: cachetools.TTLCache(maxsize=256, ttl=600)
    )


def get_trade_staging_state(request: Request) -> TradeStagingState:
    return request.app.state.trade_staging


router = APIRouter(prefix="/api/trades")

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-_가-힣]+$")


async def _validate_import_groups(
    pool: asyncpg.Pool,
    user_id,
    account_id: str,
    rows: list[dict],
) -> list[ImportError]:
    """preview 시점 정합성 검증. staging rows 를 group 단위로 가상 적용 후 oversell 탐지.

    commit 시 한 번 더 동일 검증을 수행하므로 race condition 은 commit 단계에서 차단된다.
    """
    if not rows:
        return []

    errors: list[ImportError] = []
    groups: dict[TradeGroupKey, list[dict]] = defaultdict(list)
    for row in rows:
        group_key = TradeGroupKey(
            account_id=account_id,
            ticker=row["ticker_symbol"],
            asset_name=row["asset_name"],
            country=row["country_code"],
        )
        groups[group_key].append(row)

    now = datetime.now(timezone.utc)
    async with acquire_for_user(pool, user_id) as conn:
        await assert_account_exists(conn, account_id)
        for group_key, group_rows in groups.items():
            group_existing = await list_trades_in_group(conn, user_id, group_key)
            existing_by_sig: dict = {
                trade_to_signature(t, account_id): t for t in group_existing
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
                        virtual_merged.append(existing.model_copy(update=patch))
                    continue
                if sig in seen_sigs:
                    continue
                seen_sigs.add(sig)
                virtual_inserts.append(Trade(
                    id=f"__pending_preview_{i}",
                    user_id=str(user_id),
                    account_id=account_id,
                    asset_name=row["asset_name"],
                    ticker_symbol=row["ticker_symbol"],
                    market_type=row["market_type"],
                    trade_type=row["trade_type"],
                    price=row["price"],
                    quantity=row["quantity"],
                    total_amount=row["price"] * row["quantity"],
                    traded_at=traded_at_utc,
                    commission=row["commission"],
                    tax=row["tax"],
                    country_code=row["country_code"],
                    exchange=row["exchange"],
                    created_at=now,
                    updated_at=now,
                ))

            virtual_merged_ids = {m.id for m in virtual_merged}
            virtual_fresh = (
                virtual_merged
                + [t for t in group_existing if t.id not in virtual_merged_ids]
                + virtual_inserts
            )
            oversell_msg = _find_import_oversell(virtual_fresh, group_key)
            if oversell_msg is not None:
                errors.append(ImportError(row_no=0, reason=oversell_msg))

    return errors


def _find_import_oversell(
    trades: list[Trade], key: TradeGroupKey
) -> str | None:
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
                "이전 매수 거래가 누락된 것 같으니 거래내역서 기간을 더 길게 받아 다시 시도해주세요."
            )
        if ev.oversell:
            return (
                f"{asset} {traded_date} 매도 수량이 보유 수량을 초과합니다. "
                "이전 매수 거래가 누락된 것 같으니 거래내역서 기간을 더 길게 받아 다시 시도해주세요."
            )
    return None


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
        accounts = await repo_list_accounts(conn)

    return {"trades": [_trade_with_account_dict(t) for t in trades], "accounts": accounts}


@router.post("", status_code=201)
async def create_trade(
    data: TradeCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        await assert_account_exists(conn, data.account_id)

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
        })

        fresh_trades = [*group_trades, new_trade.model_copy(update={"id": row["id"]})]
        await recalc_group_pnl(conn, fresh_trades, group_key)

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

    breakdown = compute_flexible_breakdown(sell)
    evaluation = evaluate_strategy_for_sell(sell, None)

    return TradeSummaryResponse.model_validate({
        "pnl": breakdown.pnl,
        "result": sell.result,
        "holding_days": sell.holding_days,
        "strategy_evaluation": evaluation,
        "breakdown": breakdown,
    })


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

        patch, fields = strip_sell_auto_derived(patch, fields, existing.trade_type)
        if not patch:
            return Response(status_code=204)

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
            await recalc_group_pnl(conn, fresh_trades, key)
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
        ok, msg, _ = validate_mutation(group_trades, "delete", target)
        if not ok:
            raise APIError(msg, 400)

        await delete_trade(conn, trade_id, user.id)

        remaining = [t for t in group_trades if t.id != trade_id]
        await recalc_group_pnl(conn, remaining, key)

    return Response(status_code=204)


# ── Import endpoints ──────────────────────────────────────────────────────────

@router.post("/import/preview")
async def import_preview(
    file: UploadFile = File(...),
    broker_key: str | None = None,
    account_id: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    staging: TradeStagingState = Depends(get_trade_staging_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
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

    detected_key = broker_key or detect_broker(filename, file_bytes)
    if not detected_key or detected_key not in PARSERS:
        raise APIError("증권사를 자동으로 감지하지 못했습니다. broker_key를 명시해주세요.", 400)

    parser = PARSERS[detected_key]
    # 동기 pdfplumber/openpyxl 파싱은 threadpool 로 — async 이벤트 루프 비차단
    parse_result = await run_in_threadpool(parser.parse, file_bytes, filename)

    now_utc = datetime.now(timezone.utc)

    # ticker 해결 (lifespan-managed 공유 httpx client 사용)
    asset_names = {t.asset_name for t in parse_result.trades}
    ticker_hints = {t.asset_name: t.ticker_hint for t in parse_result.trades if t.ticker_hint}

    ticker_map = await resolve_tickers(asset_names, ticker_hints, client=http_client)

    # 기존 거래에서 시그니처 셋 구성 (중복 판단용)
    # 파싱 결과의 KST 일자 min/max 범위로만 fetch — 사용자 전체 trades fetch 회피.
    parsed_kst_dates: list[date] = [
        d
        for pt in parse_result.trades
        if (d := parse_kst_date(pt.traded_at_kst)) is not None
    ]

    if parsed_kst_dates:
        # KST 일자 범위 [min 00:00, max+1 00:00) 로 변환 — 사용자가 KST 어느 시각에 등록한 거래든 포함
        midnight = time(0, 0)
        date_from_utc = kst_date_to_utc(min(parsed_kst_dates), midnight)
        date_to_utc = kst_date_to_utc(max(parsed_kst_dates) + timedelta(days=1), midnight)

        async with acquire_for_user(pool, user.id) as conn:
            all_trades = await list_trades(
                conn, user.id, date_from=date_from_utc, date_to=date_to_utc
            )
    else:
        all_trades = []

    # account_id 없이 ticker+날짜+거래유형+수량+가격으로 근사 dedup.
    # commit 시 정확한 account_id 기반 dedup이 재실행되므로 이는 참고용 카운트.
    existing_sigs: set = {trade_to_preview_signature(t) for t in all_trades}

    rows_to_stage: list[dict] = []
    dup_count = 0
    unresolved_ticker_count = 0
    parse_errors: list[ImportError] = [
        ImportError(row_no=e["row_no"], reason=e["reason"])
        for e in parse_result.errors
    ]

    for pt in parse_result.trades:
        ticker = ticker_map.get(pt.asset_name)
        if ticker is None:
            unresolved_ticker_count += 1
            parse_errors.append(ImportError(
                row_no=pt.source_row_no,
                reason=f"ticker 미해결: {pt.asset_name} — 종목명에서 코드를 찾지 못함",
            ))
            continue

        # traded_at 파싱 (KST → UTC)
        traded_date = parse_kst_date(pt.traded_at_kst)
        if traded_date is None:
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason=f"날짜 파싱 오류: {pt.traded_at_kst}"))
            continue
        kst_str = pt.traded_at_kst[:10]  # "YYYY-MM-DD" — staging 시 commit 경로에서 재사용
        # 시각 정보가 함께 들어온 경우만 보관 (머지 시 traded_at 정밀도 갱신용)
        kst_full = pt.traded_at_kst if len(pt.traded_at_kst) > 10 else None

        if traded_date > now_utc.date():
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason="미래 일자 거래 등록 불가"))
            continue

        preview_sig = make_preview_signature(
            trade_date=traded_date,
            ticker=ticker,
            asset_name=pt.asset_name,
            trade_type=pt.trade_type,
            quantity=pt.quantity,
            price=pt.price,
        )
        if preview_sig in existing_sigs:
            dup_count += 1

        # 근사 중복이어도 staging — commit 시 account_id 기반 정확한 dedup 수행
        row_data = {
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
            "country_code": DEFAULT_COUNTRY,
            "exchange": "",
            "_sig_date": kst_str,
            "_sig_ticker": ticker,
            "_sig_asset": pt.asset_name,
        }
        rows_to_stage.append(row_data)

    staging_id = str(uuid.uuid4())
    staging.cache[staging_id] = {
        "user_id": str(user.id),
        "rows": rows_to_stage,
        "parse_errors": [e.model_dump() for e in parse_errors],
        "usd_skip_count": parse_result.usd_skip_count,
        "broker_key": detected_key,
        "account_hint": parse_result.account_hint,
    }

    # 계좌가 지정되었으면 사용자에게 commit 전에 정합성 위반을 노출한다.
    validation_errors: list[ImportError] = []
    if account_id:
        validation_errors = await _validate_import_groups(
            pool, user.id, account_id, rows_to_stage
        )

    return ImportPreviewResponse(
        staging_id=staging_id,
        broker_key=detected_key,
        broker_name=parser.display_name,
        account_hint=parse_result.account_hint,
        new_count=len(rows_to_stage) - dup_count,
        duplicate_count=dup_count,
        error_count=len(parse_errors),
        usd_skip_count=parse_result.usd_skip_count,
        unresolved_ticker_count=unresolved_ticker_count,
        errors=parse_errors,
        validation_errors=validation_errors,
    )


@router.post("/import/commit")
async def import_commit(
    body: ImportCommitRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    staging: TradeStagingState = Depends(get_trade_staging_state),
) -> ImportCommitResponse:
    """preview에서 staging된 거래를 실제로 INSERT한다."""
    staged = staging.cache.get(body.staging_id)
    if staged is None:
        raise APIError("staging이 만료되었거나 존재하지 않습니다. 파일을 다시 업로드해주세요.", 400)
    if staged["user_id"] != str(user.id):
        raise APIError("권한이 없습니다.", 403)

    rows: list[dict] = staged["rows"]
    usd_skip_count: int = staged["usd_skip_count"]
    commit_errors: list[ImportError] = []
    inserted_count = 0
    merged_count = 0
    skipped_count = 0

    async with acquire_for_user(pool, user.id) as conn:
        await assert_account_exists(conn, body.account_id)

        # staged rows를 (account_id, ticker, country) 그룹으로 분할 후 그룹별로 처리
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
            # 그룹별로 기존 거래 페치 → 시그니처→Trade 매핑 구성 (사용자 전체 fetch 회피)
            group_existing = await list_trades_in_group(conn, user.id, group_key)
            existing_by_sig: dict = {
                trade_to_signature(t, str(body.account_id)): t for t in group_existing
            }
            # 같은 batch 내 중복 INSERT 방지용 (DB + 직전 INSERT 결정 모두 포함)
            seen_sigs: set = set(existing_by_sig.keys())

            # BUY → SELL 순 정렬
            group_rows.sort(key=lambda r: (r["traded_at_kst"], 0 if r["trade_type"] == TRADE_TYPE_BUY else 1))

            to_insert: list[dict] = []
            to_merge: list[tuple[Trade, dict]] = []
            for row in group_rows:
                kst_str = row["traded_at_kst"]
                traded_date = date.fromisoformat(kst_str)

                # 파일 체결 시각 → UTC. 시각 없으면 KST 장 시작(09:00) 고정.
                kst_full = row.get("traded_at_kst_full")
                if kst_full:
                    kst_dt = datetime.fromisoformat(kst_full)
                    traded_at_utc = kst_date_to_utc(kst_dt.date(), kst_dt.time())
                    # build_merge_patch 가 traded_at 비교를 위해 사용하는 키
                    row_for_merge = {**row, "traded_at_utc": traded_at_utc}
                else:
                    traded_at_utc = kst_date_to_utc(traded_date)
                    row_for_merge = row  # traded_at_utc 키 없음 → 머지에서 traded_at 비교 안 함

                sig = make_signature(
                    account_id=str(body.account_id),
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
                        to_merge.append((existing, patch))
                    else:
                        # 완전히 동일 → noop
                        skipped_count += 1
                    continue

                if sig in seen_sigs:
                    # 같은 import batch 내에서 같은 시그니처가 또 등장 → skip
                    skipped_count += 1
                    continue

                insert_row = {
                    "account_id": str(body.account_id),
                    "asset_name": row["asset_name"],
                    "ticker_symbol": row["ticker_symbol"],
                    "market_type": row["market_type"],
                    "trade_type": row["trade_type"],
                    "price": row["price"],
                    "quantity": row["quantity"],
                    "traded_at": traded_at_utc,
                    "commission": row["commission"],
                    "tax": row["tax"],
                    "country_code": row["country_code"],
                    "exchange": row["exchange"],
                }
                to_insert.append(insert_row)
                seen_sigs.add(sig)

            if not to_insert and not to_merge:
                continue

            # 정합성 검증은 DB 적용 *전* 가상 적용으로 수행한다.
            # acquire_for_user 가 이미 outer transaction 을 잡고 있어 inner
            # conn.transaction() 의 SAVEPOINT 동작이 Supavisor pooler 환경에서
            # 안정적이지 않을 수 있어, "검증 실패면 raise → rollback" 패턴을 피한다.
            now_for_virtual = datetime.now(timezone.utc)
            virtual_inserts = [
                Trade(
                    id=f"__pending_{i}",
                    user_id=str(user.id),
                    total_amount=r["price"] * r["quantity"],
                    created_at=now_for_virtual,
                    updated_at=now_for_virtual,
                    **r,
                )
                for i, r in enumerate(to_insert)
            ]
            virtual_merged = [
                existing.model_copy(update=patch) for existing, patch in to_merge
            ]
            virtual_merged_ids = {m.id for m in virtual_merged}
            virtual_fresh = (
                virtual_merged
                + [t for t in group_existing if t.id not in virtual_merged_ids]
                + virtual_inserts
            )
            oversell_msg = _find_import_oversell(virtual_fresh, group_key)
            if oversell_msg is not None:
                commit_errors.append(ImportError(row_no=0, reason=oversell_msg))
                continue

            # 검증 통과 → 실제 DB 적용
            err_asset = (
                to_insert[0]["asset_name"]
                if to_insert
                else (to_merge[0][0].asset_name if to_merge else group_key.asset_name)
            )
            try:
                async with conn.transaction():
                    await acquire_trade_group_lock(conn, str(user.id), group_key)

                    # 1) 머지: 기존 거래 update
                    merged_trades: list[Trade] = []
                    for existing, patch in to_merge:
                        await update_trade_from_import(
                            conn, str(existing.id), str(user.id), patch
                        )
                        merged_trades.append(existing.model_copy(update=patch))

                    # 2) 신규 INSERT
                    if to_insert:
                        inserted_trades = await insert_trades_bulk(
                            conn, str(user.id), to_insert
                        )
                    else:
                        inserted_trades = []

                    # 3) recalc 입력: 머지된 거래는 갱신값으로, 머지 안된 기존은 그대로
                    merged_ids = {m.id for m in merged_trades}
                    fresh_trades = (
                        merged_trades
                        + [t for t in group_existing if t.id not in merged_ids]
                        + list(inserted_trades)
                    )
                    await recalc_group_pnl(conn, fresh_trades, group_key)

                    inserted_count += len(inserted_trades)
                    merged_count += len(merged_trades)
            except asyncpg.LockNotAvailableError:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 처리 중 충돌 — 잠시 후 다시 시도해주세요."))
            except asyncpg.UniqueViolationError:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 중복 거래 감지 — 이미 등록된 거래가 있습니다."))
            except asyncpg.PostgresError as e:
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} DB 오류 ({e.sqlstate}): {e.args[0] if e.args else e}"))
            except Exception:
                logger.exception("import commit 처리 오류 user_id=%s asset=%s", user.id, err_asset)
                commit_errors.append(ImportError(row_no=0, reason=f"{err_asset} 처리 오류 — 잠시 후 다시 시도해주세요."))

    del staging.cache[body.staging_id]

    return ImportCommitResponse(
        inserted_count=inserted_count,
        merged_count=merged_count,
        skipped_count=skipped_count + usd_skip_count,
        error_count=len(commit_errors),
        errors=commit_errors,
    )
