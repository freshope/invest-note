"""관리자 트리거 라우터 — 종목 마스터 적재를 백그라운드로 시작."""
from __future__ import annotations

import logging
from datetime import date

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from invest_note_api.auth.admin import require_admin, require_admin_token
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import admin_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.admin import (
    AdminListResponse,
    AdminStats,
    NpsUnmatchedCreate,
    NpsUnmatchedUpdate,
    StockUpdate,
    UserGrowthPoint,
)
from invest_note_api.services.daily_price_seed import seed_daily_prices
from invest_note_api.services.nps_seed import reconcile_nps_unmatched, seed_nps
from invest_note_api.services.stock_seed import seed, validate_seed_sources

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


async def run_seed(db_url: str, api_key: str, sources: list[str] | None = None) -> None:
    """백그라운드 적재 래퍼 — CLI 와 동일하게 seed()가 자체 asyncpg.connect 로 동작.

    풀(Depends(get_pool)) 을 쓰지 않는다 — seed 가 session advisory lock 을 수 분 보유하므로
    요청 풀을 차용하면 풀 고갈·lock leak 이 발생한다. 실패가 silent 로 묻히지 않게 로깅한다.
    """
    try:
        await seed(db_url, api_key=api_key, sources=sources)
    except Exception:
        logger.exception("admin seed/stocks 백그라운드 실행 실패")


@router.post("/seed/stocks", status_code=202)
async def trigger_seed_stocks(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    # 소스 오타는 background 에서 로그로만 남고 202 가 나가므로 트리거 시점에 검증 → 400.
    try:
        validate_seed_sources(settings.stock_seed_source_list)
    except ValueError as e:
        raise APIError(str(e), 400)
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    background_tasks.add_task(
        run_seed, db_url, settings.data_go_kr_api_key, settings.stock_seed_source_list
    )
    return {"status": "started"}


async def run_seed_nps(db_url: str, api_key: str, provider: str = "odcloud") -> None:
    """백그라운드 NPS 적재 래퍼 — reconcile(과거사명 매핑) 선행 후 seed_nps.

    reconcile 이 관리자가 채운 resolved_ticker 를 먼저 해소하며 과거사명을 stock_aliases 에
    등록하면, 스냅샷 갱신 시 이어지는 seed 매칭(resolve_tickers→stocks_repo.search, 별칭 통합
    검색)이 그 별칭으로 자동 해소해 같은 종목이 nps_unmatched 에 다시 쌓이지 않는다.
    reconcile 실패는 seed 를 막지 않는다(독립 로깅) — upsert_nps_unmatched 가 resolved_ticker
    를 보존(holding_level 만 갱신)해 큐레이션 유실이 없다. 둘 다 자체 asyncpg.connect 로 순차
    동작(seed/stocks 와 동일 이유, advisory lock 충돌 없음).
    """
    try:
        await reconcile_nps_unmatched(db_url)
    except Exception:
        logger.exception("admin seed/nps 선행 reconcile 실패 — seed 는 계속 진행")
    try:
        await seed_nps(db_url, api_key=api_key, provider=provider)
    except Exception:
        logger.exception("admin seed/nps 백그라운드 실행 실패")


@router.post("/seed/nps", status_code=202)
async def trigger_seed_nps(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    background_tasks.add_task(
        run_seed_nps, db_url, settings.data_go_kr_api_key, settings.nps_provider
    )
    return {"status": "started"}


async def run_seed_daily_prices(
    db_url: str,
    api_key: str,
    primary_provider: str = "data_go_kr",
    gap_provider: str = "naver",
    us_primary_provider: str = "yahoo",
) -> None:
    """백그라운드 일별 종가 사전 적재 래퍼 — 전체 유저 보유종목 union 2년치."""
    try:
        await seed_daily_prices(
            db_url,
            api_key=api_key,
            primary_provider=primary_provider,
            gap_provider=gap_provider,
            us_primary_provider=us_primary_provider,
        )
    except Exception:
        logger.exception("admin seed/daily-prices 백그라운드 실행 실패")


@router.post("/seed/daily-prices", status_code=202)
async def trigger_seed_daily_prices(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    """자산 변화 페이지 콜드스타트 완화 — 보유종목 종가 사전 적재(cron pre-warm)."""
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    background_tasks.add_task(
        run_seed_daily_prices,
        db_url,
        settings.data_go_kr_api_key,
        settings.daily_price_provider,
        settings.daily_price_gap_provider,
        settings.us_daily_price_provider,
    )
    return {"status": "started"}


@router.post("/reconcile/nps")
async def trigger_reconcile_nps(
    _: None = Depends(require_admin_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    """관리자가 nps_unmatched.resolved_ticker 를 채운 뒤 호출 — 과거사명 매핑을 즉시 해소.

    seed 와 달리 가볍고(자체 connect, 수십 건) 결과 확인이 유용하므로 동기 실행 후 통계를 반환한다.
    """
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await reconcile_nps_unmatched(db_url)


# ─────────────────────────── 어드민 패널 CRUD (require_admin = JWT + allowlist) ───────────────────────────
#
# 위 트리거(/admin/seed/*, /admin/reconcile/nps)는 머신용 X-Admin-Token 경로로 그대로 둔다.
# 아래는 운영자 웹 패널용 — Supabase JWT + ADMIN_EMAILS allowlist 게이트(require_admin).
# RLS 제거 후 메인 풀(invest_note_app=owner) plain connection 이 cross-user 무필터 조회한다.

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
