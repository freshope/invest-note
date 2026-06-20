"""app-config 라우터 — 강제 업데이트용 public 엔드포인트(인증 없음)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from invest_note_api.config import Settings, get_settings
from invest_note_api.schemas.app_config import AppConfigResponse, StoreUrls

router = APIRouter()


@router.get("/app-config", response_model=AppConfigResponse)
async def get_app_config(settings: Settings = Depends(get_settings)) -> AppConfigResponse:
    return AppConfigResponse(
        min_supported_version=settings.min_supported_version,
        store_url=StoreUrls(
            ios=settings.store_url_ios,
            android=settings.store_url_android,
        ),
        be_auth_enabled=settings.be_auth_enabled,
    )
