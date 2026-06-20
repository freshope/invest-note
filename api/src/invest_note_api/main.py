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
from invest_note_api.external.fx import FxCacheState, validate_fx_providers
from invest_note_api.external.quotes import QuoteCacheState, validate_quote_providers
from invest_note_api.routers import accounts, admin, admin_board, app_config, auth, health, live_update, me
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
        validate_quote_providers(
            settings.quote_provider_list, settings.us_quote_provider_list
        )
        validate_fx_providers(settings.fx_provider_list)
        validate_daily_price_providers(
            settings.daily_price_provider,
            settings.daily_price_gap_provider,
            settings.us_daily_price_provider,
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
        app.state.fx_cache = FxCacheState()
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

    # 앱(인증) 라우터 — 정식 경로는 /v1/*, 기존 경로는 하위호환 숨김 alias.
    app_routers = (me.router, accounts.router, trades.router, portfolio.router, stocks.router, analysis.router, assets.router)

    application.include_router(health.router)
    # OAuth 중개 라우터(/auth/login·callback·token·refresh) — 모두 무인증(로그인 진입점).
    # health(JWKS) 다음, 인증 보호 라우터(/v1·/me) 앞에 mount.
    application.include_router(auth.router)
    application.include_router(app_config.router)
    # OTA 매니페스트 — public(인증 없음). app_config 처럼 legacy `/api` alias 미등록
    # (FE 플러그인이 절대경로 `/live-update/manifest` 를 굽는다 — _workspace/03_fe_changes.md).
    application.include_router(live_update.router)

    # 정식: /v1/* (스키마 노출)
    for app_router in app_routers:
        application.include_router(app_router, prefix="/v1")

    # admin 게시판 라우터 — admin.router 의 catch-all GET /admin/{table} 이 /admin/boards 를
    # table="boards" 로 흡수하므로 반드시 admin.router 보다 **먼저** include 한다(테스트로 가드).
    application.include_router(admin_board.router)

    # admin 트리거 라우터 — 정식 `/admin/*`(관리용). 앱 alias 들과 무관.
    application.include_router(admin.router)

    # Legacy alias — 배포된 구버전 앱 호환용. 스키마 중복 노출 방지로 include_in_schema=False.
    # bare(/xxx): 현행 FE 가 쓰던 경로. /api/xxx: 더 오래된 alias.
    # FE/모바일 앱이 모두 /v1 로 마이그레이션 완료되면 제거 예정.
    for legacy_router in app_routers:
        application.include_router(legacy_router, include_in_schema=False)
        application.include_router(legacy_router, prefix="/api", include_in_schema=False)

    return application


# 모듈 임포트 시 Settings 로딩을 피하기 위해 module-level app 생성 안 함.
# uvicorn 실행 시: uvicorn invest_note_api.main:create_app --factory
# 테스트 시: create_app(settings=test_settings) 직접 호출
