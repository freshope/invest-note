"""어드민 웹 패널 CRUD 라우터 — Supabase JWT + ADMIN_EMAILS allowlist(require_admin) 게이트."""
from __future__ import annotations

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from invest_note_api.auth.admin import require_admin
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import get_pool
from invest_note_api.db_ops import admin_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.admin import (
    AccountDeletionStats,
    AdminListResponse,
    AdminStats,
    NpsUnmatchedCreate,
    NpsUnmatchedUpdate,
    StockUpdate,
    UserGrowthPoint,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ─────────────────────────── 어드민 패널 CRUD (require_admin = JWT + allowlist) ───────────────────────────
#
# 운영자 웹 패널용 — Supabase JWT + ADMIN_EMAILS allowlist 게이트(require_admin).
# RLS 제거 후 메인 풀(invest_note_app=owner) plain connection 이 cross-user 무필터 조회한다.
# (seed 적재는 Coolify CLI `python -m ...stock_seed`/`nps_seed` 로만 수행 — HTTP 트리거 없음.)

ERR_NPS_EXISTS = "이미 존재하는 nps_unmatched 항목입니다."
ERR_NOT_FOUND = "해당 항목을 찾을 수 없습니다."

# URL 경로(하이픈) → admin_repo 테이블 키(언더스코어).
_TABLE_PATH = {
    "users": "users",
    "accounts": "accounts",
    "trades": "trades",
    "custom-tags": "custom_tags",
    "stocks": "stocks",
    "nps-unmatched": "nps_unmatched",
}


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> AdminStats:
    async with pool.acquire() as conn:
        return AdminStats(**await admin_repo.get_stats(conn))


@router.get("/user-growth", response_model=list[UserGrowthPoint])
async def admin_user_growth(
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[UserGrowthPoint]:
    """대시보드 누적 사용자수 차트 — 일별 누적 가입자 시계열(KST 버킷).

    `/{table}` catch-all 보다 먼저 등록해야 table="user-growth" 로 흡수되지 않는다.
    """
    async with pool.acquire() as conn:
        return [UserGrowthPoint(**p) for p in await admin_repo.get_user_growth(conn)]


@router.get("/me")
async def admin_me(
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, str | None]:
    """현재 세션이 어드민(allowlist)인지 확인하는 경량 프로브 — 비-admin 은 require_admin 이 403.

    FE 라우트 가드가 셸 진입 전 admin 여부를 판정하는 용도(DB 미접근).
    `/{table}` 보다 먼저 등록해야 `table="me"` 로 흡수되지 않는다.
    """
    return {"email": user.email}


@router.get("/deletion-stats", response_model=AccountDeletionStats)
async def admin_deletion_stats(
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> AccountDeletionStats:
    """회원 탈퇴 통계 — 누적/탈퇴율/평균 사용기간/사유 분포/일별 추이.

    `/{table}` catch-all 보다 먼저 등록해야 table="deletion-stats" 로 흡수되지 않는다.
    """
    async with pool.acquire() as conn:
        return AccountDeletionStats(**await admin_repo.get_deletion_stats(conn))


@router.get("/{table}", response_model=AdminListResponse)
async def admin_list(
    table: str,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=admin_repo.DEFAULT_PAGE_SIZE, ge=1),
    q: str | None = Query(default=None),
) -> AdminListResponse:
    table_key = _TABLE_PATH.get(table)
    if table_key is None:
        raise APIError(ERR_NOT_FOUND, 404)
    async with pool.acquire() as conn:
        rows, total = await admin_repo.list_rows(
            conn, table_key, page=page, page_size=page_size, q=q
        )
    return AdminListResponse(items=rows, total=total)


@router.patch("/stocks/{country_code}/{ticker}")
async def admin_update_stock(
    country_code: str,
    ticker: str,
    body: StockUpdate,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    fields = body.model_dump(exclude_unset=True)
    async with pool.acquire() as conn:
        row = await admin_repo.update_stock(conn, country_code, ticker, fields)
    if row is None:
        raise APIError(ERR_NOT_FOUND, 404)
    return row


@router.post("/nps-unmatched", status_code=201)
async def admin_create_nps(
    body: NpsUnmatchedCreate,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with pool.acquire() as conn:
        row = await admin_repo.create_nps_unmatched(
            conn,
            nps_name=body.nps_name,
            nps_as_of=body.nps_as_of,
            holding_level=body.holding_level,
            resolved_ticker=body.resolved_ticker,
        )
    if row is None:
        raise APIError(ERR_NPS_EXISTS, 409)
    return row


@router.patch("/nps-unmatched")
async def admin_update_nps(
    body: NpsUnmatchedUpdate,
    nps_name: str = Query(...),
    nps_as_of: date = Query(...),
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    fields = body.model_dump(exclude_unset=True)
    async with pool.acquire() as conn:
        row = await admin_repo.update_nps_unmatched(
            conn, nps_name=nps_name, nps_as_of=nps_as_of, fields=fields
        )
    if row is None:
        raise APIError(ERR_NOT_FOUND, 404)
    return row


@router.delete("/nps-unmatched", status_code=204, response_class=Response)
async def admin_delete_nps(
    nps_name: str = Query(...),
    nps_as_of: date = Query(...),
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with pool.acquire() as conn:
        deleted = await admin_repo.delete_nps_unmatched_row(
            conn, nps_name=nps_name, nps_as_of=nps_as_of
        )
    if not deleted:
        raise APIError(ERR_NOT_FOUND, 404)
    return Response(status_code=204)
