from fastapi import APIRouter, Depends

from invest_note_api.auth.be_token import build_be_jwks
from invest_note_api.config import Settings, get_settings

router = APIRouter()


# 인프라 헬스체크 — OpenAPI 문서에 노출 불필요. GET·HEAD 한 라우트로 묶으면 두 메서드가
# 같은 operation_id 를 공유해 "Duplicate Operation ID" 경고가 나므로 스키마에서 제외한다.
@router.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# BE 자체 토큰(Phase 2a) JWKS 서빙 — issuer registry 가 BE 토큰을 Supabase 와 동일 경로로
# 검증할 공개키. ⚠️ 무인증·공개(get_current_user 의존 없음, P8): BE 가 자기 토큰을 검증할 때
# 자기 JWKS 를 가져와야 하므로 인증을 걸면 순환한다. be_token_signing_key 빈 값이면 빈 keys
# 반환(dormant 안전). health 라우터에 묶어 auth 라우터와 독립 mount.
@router.get("/auth/.well-known/jwks.json", include_in_schema=False)
async def be_jwks(settings: Settings = Depends(get_settings)) -> dict:
    return build_be_jwks(settings)
