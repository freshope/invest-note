from contextlib import asynccontextmanager

from asyncpg.exceptions import LockNotAvailableError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from invest_note_api.config import Settings, get_settings
from invest_note_api.db import create_pool
from invest_note_api.errors import APIError, ERR_LOCK_BUSY, api_error_handler, validation_error_handler
from invest_note_api.external.http_client import create_http_client
from invest_note_api.external.kis import configure_kis
from invest_note_api.external.quotes import QuoteCacheState, validate_quote_providers
from invest_note_api.routers import accounts, admin, app_config, health, live_update, me
from invest_note_api.routers import trades, portfolio, stocks, analysis, assets
from invest_note_api.routers.trades import TradeStagingState
from invest_note_api.services.daily_price_seed import validate_daily_price_providers


async def lock_not_available_handler(request: Request, exc: LockNotAvailableError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": ERR_LOCK_BUSY})


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 요청 경로가 소비하는 공급자 env 오타 fail-fast — quotes 는 요청 경로가 예외를
        # 삼켜 시세가 조용히 null, daily price 는 GET /assets/history 가 사용자 대면 500 을
        # 반복하므로 부팅 시점에 검증한다. admin/batch 전용 도메인(seed 소스 등)은
        # 트리거 시점 검증으로 충분(admin.py 참조).
        validate_quote_providers(settings.quote_provider_list)
        validate_daily_price_providers(
            settings.daily_price_provider, settings.daily_price_gap_provider
        )
        # database_url이 비어 있으면 풀 생성 생략 (테스트 환경)
        if settings.database_url:
            app.state.pool = await create_pool(settings.database_url)
        else:
            app.state.pool = None
        # KIS 자격증명/도메인 설정 + 토큰 캐시 리셋 (kis 공급자 미사용 시에도 무해).
        # pool 을 넘겨 토큰을 kis_tokens 테이블에 영속화 (pool=None 이면 메모리 전용).
        configure_kis(settings, pool=app.state.pool)
        app.state.quote_cache = QuoteCacheState()
        app.state.trade_staging = TradeStagingState()
        app.state.http_client = create_http_client()
        yield
        await app.state.http_client.aclose()
        if app.state.pool is not None:
            await app.state.pool.close()

    application = FastAPI(title="invest-note API", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(LockNotAvailableError, lock_not_available_handler)

    application.include_router(health.router)
    application.include_router(app_config.router)
    # OTA 매니페스트 — public(인증 없음). app_config 처럼 legacy `/api` alias 미등록
    # (FE 플러그인이 절대경로 `/live-update/manifest` 를 굽는다 — _workspace/03_fe_changes.md).
    application.include_router(live_update.router)
    application.include_router(me.router)
    application.include_router(accounts.router)
    application.include_router(trades.router)
    application.include_router(portfolio.router)
    application.include_router(stocks.router)
    application.include_router(analysis.router)
    application.include_router(assets.router)
    # admin 트리거 라우터 — legacy `/api/*` alias 에 포함하지 않는다(관리용 신규 경로).
    application.include_router(admin.router)

    # Legacy `/api/*` 경로 alias — FE/모바일 앱 마이그레이션 완료 후 제거 예정.
    # 스키마 중복 노출 방지를 위해 include_in_schema=False.
    for legacy_router in (me.router, accounts.router, trades.router, portfolio.router, stocks.router, analysis.router, assets.router):
        application.include_router(legacy_router, prefix="/api", include_in_schema=False)

    return application


# 모듈 임포트 시 Settings 로딩을 피하기 위해 module-level app 생성 안 함.
# uvicorn 실행 시: uvicorn invest_note_api.main:create_app --factory
# 테스트 시: create_app(settings=test_settings) 직접 호출
