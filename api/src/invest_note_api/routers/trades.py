"""trades 라우터 — 6 endpoints + import (preview/commit)."""
from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone

import asyncpg
import cachetools
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
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
)
from invest_note_api.domain.holdings import (
    compute_flexible_breakdown,
    compute_holding_summary,
)
from invest_note_api.domain.analysis.strategy_adherence import evaluate_strategy_for_sell
from invest_note_api.domain.realized_pnl import (
    TradeGroupKey,
    trade_to_group_key,
    validate_mutation,
)
from invest_note_api.domain.trade_utils import kst_date_to_utc
from invest_note_api.domain.trade_import import make_signature
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    MARKET_TYPE_STOCK,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    Trade,
    trade_country,
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

# staging cache: {staging_id: {"user_id": str, "rows": list[dict], "parse_errors": list[dict]}}
_STAGING: cachetools.TTLCache = cachetools.TTLCache(maxsize=256, ttl=600)

router = APIRouter(prefix="/api/trades")

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-_가-힣]+$")


def _trade_dict(trade) -> dict:
    return trade.model_dump(mode="json")


def _trade_with_account_dict(trade) -> dict:
    d = _trade_dict(trade)
    d["account"] = {"name": d.pop("account_name", None), "broker": d.pop("account_broker", None)}
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
        trades = await list_trades_with_account(conn, user.id)
        accounts_rows = await conn.fetch(
            "SELECT * FROM accounts ORDER BY created_at ASC"
        )

    if ticker:
        trades = [
            t for t in trades
            if trade_country(t) == country
            and t.ticker_symbol == ticker
        ]

    accounts = [dict(r) for r in accounts_rows]
    for a in accounts:
        if "cash_balance" in a and a["cash_balance"] is not None:
            a["cash_balance"] = float(a["cash_balance"])

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
            account_id=data.account_id,
            asset_name=data.asset_name,
            ticker_symbol=data.ticker_symbol,
            market_type=data.market_type,
            trade_type=data.trade_type,
            price=data.price,
            quantity=data.quantity,
            total_amount=data.price * data.quantity,
            traded_at=data.traded_at,
            country_code=data.country_code or DEFAULT_COUNTRY,
            exchange=data.exchange or "",
            commission=data.commission,
            tax=data.tax,
            created_at=now,
            updated_at=now,
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

        if data.trade_type == TRADE_TYPE_SELL:
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

        fresh_trades = [*group_trades, Trade(**{**new_trade.model_dump(), "id": row["id"]})]
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
    d = _trade_dict(trade)
    account_name = d.pop("account_name", None)
    account_broker = d.pop("account_broker", None)
    d["account"] = {"name": account_name, "broker": account_broker}
    return d


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

            fresh_trades = [Trade(**{**t.model_dump(), **patch}) if t.id == trade_id else t for t in group_trades]
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
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
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
    parse_result = parser.parse(file_bytes, filename)

    now_utc = datetime.now(timezone.utc)

    # ticker 해결
    asset_names = {t.asset_name for t in parse_result.trades}
    ticker_hints = {t.asset_name: t.ticker_hint for t in parse_result.trades if t.ticker_hint}

    ticker_map = await resolve_tickers(asset_names, ticker_hints)

    async with acquire_for_user(pool, user.id) as conn:
        # 기존 거래에서 시그니처 셋 구성 (중복 판단용 — 날짜 범위는 파싱 결과 기간으로 한정)
        all_trades = await list_trades(conn, user.id)

    # account_id 없이 ticker+날짜+거래유형+수량+가격으로 근사 dedup.
    # commit 시 정확한 account_id 기반 dedup이 재실행되므로 이는 참고용 카운트.
    _PREVIEW_ACCT = "__preview__"
    existing_sigs: set = set()
    for t in all_trades:
        t_date = t.traded_at.date() if hasattr(t.traded_at, "date") else date.fromisoformat(str(t.traded_at)[:10])
        existing_sigs.add(make_signature(
            account_id=_PREVIEW_ACCT,
            trade_date=t_date,
            ticker=t.ticker_symbol,
            asset_name=t.asset_name,
            trade_type=t.trade_type,
            quantity=t.quantity,
            price=t.price,
        ))

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
        try:
            kst_str = pt.traded_at_kst[:10]  # "YYYY-MM-DD"
            traded_date = date.fromisoformat(kst_str)
        except ValueError:
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason=f"날짜 파싱 오류: {pt.traded_at_kst}"))
            continue

        if traded_date > now_utc.date():
            parse_errors.append(ImportError(row_no=pt.source_row_no, reason="미래 일자 거래 등록 불가"))
            continue

        preview_sig = make_signature(
            account_id=_PREVIEW_ACCT,
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
            "commission": pt.commission,
            "tax": pt.tax,
            "country_code": DEFAULT_COUNTRY,
            "exchange": "",
            "_sig_date": kst_str,
            "_sig_ticker": ticker,
            "_sig_asset": pt.asset_name,
        }
        rows_to_stage.append(row_data)

    # 실제 계좌 ID 없이 dedup 불가 → account_id는 commit 시 결정
    # preview 단계에서는 ticker+날짜 기준으로 근사 dedup만 수행 (account_id 고정 불가)

    staging_id = str(uuid.uuid4())
    _STAGING[staging_id] = {
        "user_id": str(user.id),
        "rows": rows_to_stage,
        "parse_errors": [e.model_dump() for e in parse_errors],
        "usd_skip_count": parse_result.usd_skip_count,
        "broker_key": detected_key,
        "account_hint": parse_result.account_hint,
    }

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
    )


@router.post("/import/commit")
async def import_commit(
    body: ImportCommitRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ImportCommitResponse:
    """preview에서 staging된 거래를 실제로 INSERT한다."""
    staged = _STAGING.get(body.staging_id)
    if staged is None:
        raise APIError("staging이 만료되었거나 존재하지 않습니다. 파일을 다시 업로드해주세요.", 400)
    if staged["user_id"] != str(user.id):
        raise APIError("권한이 없습니다.", 403)

    rows: list[dict] = staged["rows"]
    usd_skip_count: int = staged["usd_skip_count"]
    commit_errors: list[ImportError] = []
    inserted_count = 0
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
            # 그룹별로 기존 거래 페치 → sig 셋 구성 (사용자 전체 fetch 회피)
            group_existing = await list_trades_in_group(conn, user.id, group_key)
            existing_sigs: set = set()
            for t in group_existing:
                existing_sigs.add(make_signature(
                    account_id=str(body.account_id),
                    trade_date=t.traded_at.date(),
                    ticker=t.ticker_symbol,
                    asset_name=t.asset_name,
                    trade_type=t.trade_type,
                    quantity=t.quantity,
                    price=t.price,
                ))

            # BUY → SELL 순 정렬
            group_rows.sort(key=lambda r: (r["traded_at_kst"], 0 if r["trade_type"] == TRADE_TYPE_BUY else 1))

            to_insert: list[dict] = []
            for row in group_rows:
                kst_str = row["traded_at_kst"]
                traded_date = date.fromisoformat(kst_str)

                sig = make_signature(
                    account_id=str(body.account_id),
                    trade_date=traded_date,
                    ticker=row["ticker_symbol"],
                    asset_name=row["asset_name"],
                    trade_type=row["trade_type"],
                    quantity=row["quantity"],
                    price=row["price"],
                )
                if sig in existing_sigs:
                    skipped_count += 1
                    continue

                # 파일에 체결 시각이 없으므로 KST 장 시작 시간(09:00)으로 고정
                traded_at_utc = kst_date_to_utc(traded_date)

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
                existing_sigs.add(sig)

            if not to_insert:
                continue

            # 그룹 lock + bulk insert + recalc (savepoint로 그룹 단위 롤백)
            try:
                async with conn.transaction():
                    await acquire_trade_group_lock(conn, str(user.id), group_key)
                    inserted_trades = await insert_trades_bulk(conn, str(user.id), to_insert)
                    inserted_count += len(inserted_trades)
                    await recalc_group_pnl(conn, [*group_existing, *inserted_trades], group_key)
            except asyncpg.LockNotAvailableError:
                commit_errors.append(ImportError(row_no=0, reason=f"{to_insert[0]['asset_name']} 처리 중 충돌 — 잠시 후 다시 시도해주세요."))
            except asyncpg.UniqueViolationError:
                commit_errors.append(ImportError(row_no=0, reason=f"{to_insert[0]['asset_name']} 중복 거래 감지 — 이미 등록된 거래가 있습니다."))
            except asyncpg.PostgresError as e:
                commit_errors.append(ImportError(row_no=0, reason=f"{to_insert[0]['asset_name']} DB 오류 ({e.sqlstate}): {e.args[0] if e.args else e}"))
            except Exception:
                logger.exception("import commit 처리 오류 user_id=%s asset=%s", user.id, to_insert[0]["asset_name"])
                commit_errors.append(ImportError(row_no=0, reason=f"{to_insert[0]['asset_name']} 처리 오류 — 잠시 후 다시 시도해주세요."))

    del _STAGING[body.staging_id]

    return ImportCommitResponse(
        inserted_count=inserted_count,
        skipped_count=skipped_count + usd_skip_count,
        error_count=len(commit_errors),
        errors=commit_errors,
    )
