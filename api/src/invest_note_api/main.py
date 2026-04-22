from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from invest_note_api.config import Settings, get_settings
from invest_note_api.db import create_pool
from invest_note_api.errors import APIError, api_error_handler, validation_error_handler
from invest_note_api.routers import accounts, health, me
from invest_note_api.routers import trades, portfolio, stocks


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # database_url이 비어 있으면 풀 생성 생략 (테스트 환경)
        if settings.database_url:
            app.state.pool = await create_pool(settings.database_url)
        else:
            app.state.pool = None
        yield
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

    application.include_router(health.router)
    application.include_router(me.router)
    application.include_router(accounts.router)
    application.include_router(trades.router)
    application.include_router(portfolio.router)
    application.include_router(stocks.router)

    return application


# 모듈 임포트 시 Settings 로딩을 피하기 위해 module-level app 생성 안 함.
# uvicorn 실행 시: uvicorn invest_note_api.main:create_app --factory
# 테스트 시: create_app(settings=test_settings) 직접 호출
