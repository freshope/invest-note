from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from invest_note_api.config import Settings, get_settings
from invest_note_api.routers import health, me


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    application = FastAPI(title="invest-note API")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(me.router)

    return application


# 모듈 임포트 시 Settings 로딩을 피하기 위해 module-level app 생성 안 함.
# uvicorn 실행 시: uvicorn invest_note_api.main:create_app --factory
# 테스트 시: create_app(settings=test_settings) 직접 호출
