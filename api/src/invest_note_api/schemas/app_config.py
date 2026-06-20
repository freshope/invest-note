"""앱 설정(강제 업데이트) 응답 스키마."""
from __future__ import annotations

from ._base import CamelModel


class StoreUrls(CamelModel):
    ios: str
    android: str


class AppConfigResponse(CamelModel):
    min_supported_version: str
    store_url: StoreUrls
    # Phase 2b-4 cutover 플래그. CamelModel → wire 키 beAuthEnabled.
    be_auth_enabled: bool
