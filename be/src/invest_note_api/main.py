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
from invest_note_api.external.quotes import QuoteCacheState
from invest_note_api.routers import accounts, admin, app_config, health, me
from invest_note_api.routers import trades, portfolio, stocks, analysis, assets
from invest_note_api.routers.trades import TradeStagingState


async def lock_not_available_handler(request: Request, exc: LockNotAvailableError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": ERR_LOCK_BUSY})


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.quote_cache = QuoteCacheState()
        app.state.trade_staging = TradeStagingState()
        app.state.http_client = create_http_client()
        # database_url이 비어 있으면 풀 생성 생략 (테스트 환경)
        if settings.database_url:
            app.state.pool = await create_pool(settings.database_url)
        else:
            app.state.pool = None
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
