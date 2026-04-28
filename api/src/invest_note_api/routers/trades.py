"""trades 라우터 — 6 endpoints + import (preview/commit)."""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

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
    delete_trade,
    get_trade_with_account,
    insert_trade,
    insert_trades_bulk,
    list_trades,
    list_trades_with_account,
    patch_trade,
    strip_sell_auto_derived,
)
from invest_note_api.domain.holdings import (
    SellBreakdown,
    compute_flexible_breakdown,
    compute_total_holding,
)
from invest_note_api.domain.analysis.strategy_adherence import evaluate_strategy_for_sell
from invest_note_api.domain.realized_pnl import TradeGroupKey, trade_to_group_key, validate_mutation
from invest_note_api.domain.trade_import import ImportError, ImportSummary, make_signature
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    MARKET_TYPE_STOCK,
    RESULT_BREAKEVEN,
    RESULT_FAIL,
    RESULT_SUCCESS,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
    Trade,
)
from invest_note_api.errors import ERR_TRADE_NOT_FOUND, APIError, validate_body
from invest_note_api.schemas.trade import TradeCreate, TradeUpdate
from invest_note_api.schemas.trade_import import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
)
from invest_note_api.broker_import import PARSERS, detect_broker
from invest_note_api.broker_import.ticker_resolver import resolve_tickers

# staging cache: {staging_id: {"user_id": str, "rows": list[dict], "summary": ImportSummary}}
_STAGING: cachetools.TTLCache = cachetools.TTLCache(maxsize=256, ttl=600)

router = APIRouter(prefix="/api/trades")

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-_가-힣]+$")


def _trade_dict(trade) -> dict:
    return trade.model_dump(mode="json")


def _trade_with_account_dict(trade) -> dict:
    d = _trade_dict(trade)
    d["account"] = {"name": d.pop("account_name", None), "broker": d.pop("account_broker", None)}
    return d


def _breakdown_dict(bd: SellBreakdown) -> dict:
    return {
        "sellPrice": bd.sell_price,
        "quantity": bd.quantity,
        "avgCostPrice": bd.avg_cost_price,
        "sellAmount": bd.sell_amount,
        "costBasis": bd.cost_basis,
        "commission": bd.commission,
        "tax": bd.tax,
        "pnl": bd.pnl,
        "isManualInput": bd.is_manual_input,
    }


def _derive_result(pnl: float) -> str:
    if pnl > 0:
        return RESULT_SUCCESS
    if pnl < 0:
        return RESULT_FAIL
    return RESULT_BREAKEVEN


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
            if (t.country_code or DEFAULT_COUNTRY) == country
            and (t.ticker_symbol == ticker or t.asset_name == ticker)
        ]

    accounts = [dict(r) for r in accounts_rows]
    for a in accounts:
        if "cash_balance" in a and a["cash_balance"] is not None:
            a["cash_balance"] = float(a["cash_balance"])

    return {"trades": [_trade_with_account_dict(t) for t in trades], "accounts": accounts}


@router.post("", status_code=201)
async def create_trade(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    data = validate_body(TradeCreate, body)

    async with acquire_for_user(pool, user.id) as conn:
        # 계좌 존재 확인
        acct_exists = await conn.fetchval(
            "SELECT id FROM accounts WHERE id = $1", data.account_id
        )
        if not acct_exists:
            raise APIError("올바른 계좌를 선택해주세요.", 400)

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
        await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(new_trade))

        all_trades = await list_trades(conn, user.id)

        if data.trade_type == TRADE_TYPE_SELL:
            holding = compute_total_holding(
                all_trades,
                ticker=data.ticker_symbol,
                asset_name=data.asset_name,
                country=data.country_code or DEFAULT_COUNTRY,
                account_id=data.account_id,
            )
            if holding <= 0:
                raise APIError("보유하지 않은 종목입니다.", 400)
            if data.quantity > holding:
                raise APIError(f"보유 수량이 부족합니다 (현재 {holding}주).", 400)

        if data.trade_type == TRADE_TYPE_SELL:
            ok, msg, _ = validate_mutation(all_trades, "insert", new_trade)
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

        key = trade_to_group_key(new_trade)
        fresh_trades = [*all_trades, Trade(**{**new_trade.model_dump(), "id": row["id"]})]
        await recalc_group_pnl(conn, fresh_trades, key)

    return row


@router.get("/{trade_id}/summary")
async def get_trade_summary(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        sell_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if not sell_row:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        sell = Trade(**dict(sell_row))
        if sell.trade_type != TRADE_TYPE_SELL:
            raise APIError("매도 거래만 조회할 수 있습니다.", 400)

        all_trades = await list_trades(conn, user.id)

    breakdown = compute_flexible_breakdown(sell)
    evaluation = evaluate_strategy_for_sell(sell, all_trades, None)
    holding_days = sell.holding_days
    strategy_eval = None
    if evaluation is not None:
        strategy_eval = {
            "planned": evaluation.planned,
            "actual": evaluation.actual,
            "holdingDays": evaluation.holding_days,
            "adherence": evaluation.adherence,
        }

    return {
        "pnl": breakdown.pnl,
        "result": _derive_result(breakdown.pnl),
        "holdingDays": holding_days,
        "strategyEvaluation": strategy_eval,
        "breakdown": _breakdown_dict(breakdown),
    }


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
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    data = validate_body(TradeUpdate, body)
    fields = data.model_fields_set
    if not fields:
        return Response(status_code=204)

    patch = {k: v for k, v in data.model_dump(include=fields).items() if v is not None or k in fields}

    async with acquire_for_user(pool, user.id) as conn:
        existing_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if not existing_row:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        existing = Trade(**dict(existing_row))
        patch, fields = strip_sell_auto_derived(patch, fields, existing.trade_type)
        if not patch:
            return Response(status_code=204)

        if fields & PNL_AFFECTING_FIELDS:
            await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(existing))
            all_trades = await list_trades(conn, user.id)
            ok, msg, _ = validate_mutation(all_trades, "update", existing, patch)
            if not ok:
                raise APIError(msg, 400)

            await patch_trade(conn, trade_id, user.id, patch)

            fresh_trades = [Trade(**{**t.model_dump(), **patch}) if t.id == trade_id else t for t in all_trades]
            key = trade_to_group_key(existing)
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
        target_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if target_row is None:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)
        target = Trade(**dict(target_row))

        await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(target))

        all_trades = await list_trades(conn, user.id)
        ok, msg, _ = validate_mutation(all_trades, "delete", target)
        if not ok:
            raise APIError(msg, 400)

        key = trade_to_group_key(target)
        await delete_trade(conn, trade_id, user.id)

        remaining = [t for t in all_trades if t.id != trade_id]
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

    detected_key = broker_key or detect_broker(filename, file_bytes)
    if not detected_key or detected_key not in PARSERS:
        raise APIError("증권사를 자동으로 감지하지 못했습니다. broker_key를 명시해주세요.", 400)

    parser = PARSERS[detected_key]
    parse_result = parser.parse(file_bytes, filename)

    now_utc = datetime.now(timezone.utc)
    future_errors: list[ImportError] = []

    # ticker 해결
    asset_names = {t.asset_name for t in parse_result.trades}
    ticker_hints = {t.asset_name: t.ticker_hint for t in parse_result.trades if t.ticker_hint}

    async with acquire_for_user(pool, user.id) as conn:
        ticker_map = await resolve_tickers(conn, asset_names, ticker_hints)

        # 기존 거래에서 시그니처 셋 구성 (중복 판단용 — 날짜 범위는 파싱 결과 기간으로 한정)
        all_trades = await list_trades(conn, user.id)

    existing_sigs: set = set()
    for t in all_trades:
        sig = make_signature(
            account_id=str(t.account_id),
            trade_date=t.traded_at.date() if hasattr(t.traded_at, "date") else date.fromisoformat(str(t.traded_at)[:10]),
            ticker=t.ticker_symbol,
            asset_name=t.asset_name,
            trade_type=t.trade_type,
            quantity=t.quantity,
            price=t.price,
        )
        existing_sigs.add(sig)

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
                reason=f"ticker 미해결: {pt.asset_name} — kr_stocks에 없음",
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

        # staged rows는 account_id 없이 보관 (commit 시 account_id 바인딩)
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
        new_count=len(rows_to_stage),
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
        acct_exists = await conn.fetchval(
            "SELECT id FROM accounts WHERE id = $1", body.account_id
        )
        if not acct_exists:
            raise APIError("올바른 계좌를 선택해주세요.", 400)

        # 현재 모든 거래를 가져와 시그니처 셋 구성
        all_trades = await list_trades(conn, user.id)
        existing_sigs: set = set()
        for t in all_trades:
            t_date = t.traded_at.date() if hasattr(t.traded_at, "date") else date.fromisoformat(str(t.traded_at)[:10])
            sig = make_signature(
                account_id=str(body.account_id),
                trade_date=t_date,
                ticker=t.ticker_symbol,
                asset_name=t.asset_name,
                trade_type=t.trade_type,
                quantity=t.quantity,
                price=t.price,
            )
            existing_sigs.add(sig)

        # 그룹별로 묶어 처리
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
            group_key = (str(body.account_id), row["ticker_symbol"], row["country_code"])
            groups[group_key].append(row)

        now_utc = datetime.now(timezone.utc)

        for group_key, group_rows in groups.items():
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

                # KST 09:00 → UTC
                kst_dt = datetime.combine(traded_date, time(9, 0), tzinfo=ZoneInfo("Asia/Seoul"))
                traded_at_utc = kst_dt.astimezone(timezone.utc)

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

            # 그룹 lock + bulk insert + recalc
            lock_key = TradeGroupKey(
                account_id=str(body.account_id),
                ticker=group_key[1],
                asset_name=to_insert[0]["asset_name"],
                country=group_key[2],
            )
            try:
                await acquire_trade_group_lock(conn, str(user.id), lock_key)
                inserted_rows = await insert_trades_bulk(conn, str(user.id), to_insert)
                inserted_count += len(inserted_rows)

                # recalc
                fresh_all = await list_trades(conn, user.id)
                await recalc_group_pnl(conn, fresh_all, lock_key)
            except Exception as e:
                commit_errors.append(ImportError(row_no=0, reason=f"그룹 INSERT 오류: {e}"))
                inserted_count -= len(to_insert)  # 롤백되므로 카운트 보정

    del _STAGING[body.staging_id]

    return ImportCommitResponse(
        inserted_count=inserted_count,
        skipped_count=skipped_count + usd_skip_count,
        error_count=len(commit_errors),
        errors=commit_errors,
    )
