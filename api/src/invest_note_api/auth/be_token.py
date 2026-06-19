"""BE 자체 토큰(Phase 2a) — ES256 서명/JWKS 서빙.

token-broker 모델에서 BE 가 발급하는 토큰의 서명·검증용 JWKS 를 다룬다.
⚠️ 2a 는 dormant: mint_be_token 은 **헬퍼/테스트 전용**으로, 어떤 라우터에도 노출하지
않는다(실사용 발급 = OAuth 중개 = 2b). 검증 경로(issuer registry, auth/jwt.py)만 prod 에
얹히되 클라이언트가 BE 토큰을 발급받지 않으므로 사실상 비활성이다.

서명 alg = ES256(EC P-256). Supabase 와 동일하게 JWKS(공개키)로 검증되도록 비대칭 서명만
사용한다(HS256 금지 — verifier 분기 방지, P5). build_be_jwks 가 서빙하는 public JWK 로
registry 가 BE 토큰을 Supabase 와 동일 경로로 검증한다.
"""

import json
import time
from functools import lru_cache
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from jwt.algorithms import ECAlgorithm

from invest_note_api.config import Settings


@lru_cache(maxsize=8)
def _public_key_from_pem(pem: str):
    """PEM private key → public key 객체(F6 메모이즈). PEM 문자열로 캐시한다 — Settings 는
    pydantic v2 라 unhashable 이고 매 /v1/* 요청마다 새 인스턴스라 lru_cache 키로 못 쓴다.
    """
    return load_pem_private_key(pem.encode(), password=None).public_key()


def mint_be_token(
    sub: UUID,
    email: str | None,
    *,
    settings: Settings,
    expires_delta: int = 3600,
) -> str:
    """BE access token 발급(ES256). ⚠️ 라우터 노출 금지 — 헬퍼/테스트 전용(2a dormant).

    sub = 원래 public.users UUID(IdP sub 아님, P2 데이터 고아화 방지). iss/aud 는 BE 전용
    값(per-issuer aud, Supabase 와 구분). header.kid = be_token_kid 로 JWKS 항목과 잇는다.
    """
    if not settings.be_token_signing_key:
        raise RuntimeError("be_token_signing_key 미설정 — BE 토큰 발급 비활성(2a dormant)")

    now = int(time.time())
    payload = {
        "sub": str(sub),
        "email": email,
        "iss": settings.be_token_issuer,
        # B7: be_token_signing_key 가 있으면(위 가드 통과) be_token_audience 는 model_validator
        # 가 비어있지 않음을 보장한다. per-issuer aud 격리를 위해 "authenticated" 폴백 제거.
        "aud": settings.be_token_audience,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        settings.be_token_signing_key,
        algorithm="ES256",
        headers={"kid": settings.be_token_kid},
    )


def be_verify_key(settings: Settings):
    """BE 토큰 검증용 public key 객체(in-process 직접 주입, B8).

    ⚠️ be_jwks_uri(=supabase_url 파생 placeholder) self-fetch 를 **하지 않는다**(P8 self-HTTP
    fragility + 호스트 placeholder 동시 회피). signing key 로부터 메모리에서 public key 를 도출해
    issuer registry 의 BE entry 검증에 직접 주입한다. dormant(빈 키)면 None — registry 에 BE entry
    자체가 없어 호출되지 않는다(jwt.py 가 None 가드).

    외부 JWKS 엔드포인트(/auth/.well-known/jwks.json, build_be_jwks)는 별개로 유지된다
    (미래 외부 검증자용) — 자기검증만 이 in-process 경로를 쓴다.
    """
    if not settings.be_token_signing_key:
        return None
    return _public_key_from_pem(settings.be_token_signing_key)


def build_be_jwks(settings: Settings) -> dict:
    """BE 서명 private key 에서 public JWK set 생성.

    be_token_signing_key 가 빈 값이면 빈 keys 반환(404 아님) — dormant 안전(JWKS 엔드포인트가
    조용히 빈 키를 서빙해 Supabase 경로에 무영향).
    """
    if not settings.be_token_signing_key:
        return {"keys": []}

    private_key = load_pem_private_key(
        settings.be_token_signing_key.encode(), password=None
    )
    public_key = private_key.public_key()
    jwk = json.loads(ECAlgorithm.to_jwk(public_key))
    jwk["kid"] = settings.be_token_kid
    jwk["alg"] = "ES256"
    jwk["use"] = "sig"
    return {"keys": [jwk]}
