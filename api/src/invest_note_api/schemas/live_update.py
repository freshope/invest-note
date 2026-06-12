"""Capacitor OTA(@capgo/capacitor-updater) self-hosted 매니페스트 계약 스키마.

⚠️ 기존 `_base.py CamelModel` 을 쓰지 않는다 — Capgo 플러그인 계약은 **snake_case** 이며
요청 body 에 스키마 미정의 필드(`defaultChannel` 등)가 섞여 오므로 `extra="ignore"`.

와이어 계약 출처: `_workspace/03_fe_changes.md`(플러그인 네이티브 소스 직접 판독).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ManifestRequest(BaseModel):
    """플러그인이 앱 오픈마다 POST 하는 AppInfos body.

    결정 로직에 쓰는 두 필드만 명시하고 나머지(platform/device_id/app_id/
    version_code/defaultChannel 등)는 `extra="ignore"` 로 흡수한다. 미사용 필드를
    선언하지 않고 사용 필드에 기본값을 둬, 필드 누락·리네임 시 422 검증 표면을 없앤다
    (핸들러의 fail-open 으로 흡수 — 부팅 차단 금지).
    """

    model_config = ConfigDict(extra="ignore")

    # ★ 마케팅 버전(= App.getInfo().version). 스큐 게이트·builtin 대체의 기준값.
    #   version_code(정수 빌드번호)가 아니라 이 필드를 비교에 쓴다.
    version_build: str = ""
    # 현재 설치된 OTA 번들 버전 또는 "builtin"(적용된 OTA 없음 = 신규 스토어 설치).
    version_name: str = ""


class ManifestUpdate(BaseModel):
    """업데이트 있음 응답. 플러그인이 이 3필드로 다운로드·무결성 검증."""

    version: str
    url: str
    checksum: str


class ManifestNoUpdate(BaseModel):
    """업데이트 없음/스큐 차단 응답.

    빈 200/`{}`/204 는 플러그인이 `failed` 로 정규화하므로 금지.
    반드시 non-failure kind(`up_to_date`/`blocked`)를 실어야 한다.
    """

    kind: Literal["up_to_date", "blocked"] = "up_to_date"
