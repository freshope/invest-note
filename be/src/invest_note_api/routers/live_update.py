"""Capacitor OTA 매니페스트 결정 라우터 — public(인증 없음).

POST /live-update/manifest : 플러그인(@capgo/capacitor-updater)이 앱 오픈마다 POST.
R2 의 발행 매니페스트 JSON 을 읽어 업데이트 여부를 결정해 응답한다.

- 업데이트 있음: `{"version", "url", "checksum"}`
- 그 외(동일/구버전/스큐 차단/조회 실패): `{"kind": "up_to_date"}`

★ fail-open 원칙: manifest 조회 실패·파싱 오류·버전 비교 예외 등 **어떤 이유로든**
결정에 실패하면 no-update 를 반환한다(앱 부팅을 절대 차단하지 않는다). force-update
하드 플로어(`/app-config`)가 독립적으로 폴백을 담당한다.

스큐 게이트·builtin 대체 비교는 `version_build`(마케팅 버전)로 수행한다 — `version_code`
(정수 빌드번호) 금지. 근거: `_workspace/03_fe_changes.md`.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends

from invest_note_api.config import Settings, get_settings
from invest_note_api.external.http_client import get_http_client
from invest_note_api.schemas.live_update import ManifestNoUpdate, ManifestRequest, ManifestUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

_NO_UPDATE = ManifestNoUpdate().model_dump()


def _parse_semver(value: str) -> tuple[int, int, int]:
    """`"1.2.3"` → `(1, 2, 3)`. 누락 자리는 0, 비교 외 빌드/프리릴리스 꼬리는 무시.

    파싱 불가 시 ValueError 를 던진다(호출부가 fail-open 으로 흡수).
    """
    core = value.strip().split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return (major, minor, patch)


@router.post("/live-update/manifest", response_model=None)
async def decide_manifest(
    body: ManifestRequest,
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> dict:
    manifest_url = settings.live_update_manifest_url
    if not manifest_url:
        # env 미설정 — OTA 비활성. 조용히 no-update.
        return _NO_UPDATE

    try:
        resp = await http_client.get(manifest_url)
        resp.raise_for_status()
        manifest = resp.json()

        published_version = manifest["version"]
        required_native = manifest["required_native_version"]

        # ① 스큐 차단: 번들이 요구하는 네이티브 버전 > 기기 네이티브(version_build) → 미반환.
        #    force-update 가 폴백을 독립 담당하므로 여기서는 조용히 no-update.
        if _parse_semver(required_native) > _parse_semver(body.version_build):
            return _NO_UPDATE

        # ② effective_installed: builtin(신규 스토어 설치)은 동봉 웹 버전 = 네이티브
        #    마케팅 버전이므로 version_build 로 대체(첫 부팅 중복 다운로드 방지).
        effective_installed = (
            body.version_build if body.version_name == "builtin" else body.version_name
        )

        # ③ 발행 버전이 설치본보다 높을 때만 업데이트 반환.
        if _parse_semver(published_version) > _parse_semver(effective_installed):
            return ManifestUpdate(
                version=published_version,
                url=manifest["url"],
                checksum=manifest["checksum"],
            ).model_dump()

        # ④ 동일/구버전 → no-update.
        return _NO_UPDATE
    except Exception:  # noqa: BLE001 — fail-open: 어떤 예외든 앱 부팅 차단 금지.
        logger.warning("live-update manifest 결정 실패 — fail-open(no-update)", exc_info=True)
        return _NO_UPDATE
