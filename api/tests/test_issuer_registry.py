"""Phase 2a — issuer registry 통합 테스트(Supabase + BE 양 issuer).

검증 분기 = Supabase(default) / BE(명시 매칭). 5케이스:
  ① Supabase iss + 올바른 aud → 200(무회귀)
  ② BE iss + ES256 mint + BE aud → 200(BE 토큰이 registry 로 검증)
  ③ unknown iss → 401
  ④ aud 교차(Supabase iss + BE aud / BE iss + Supabase aud) → 401(per-issuer aud 격리, P6)
  ⑤ iss 클레임 없음 + Supabase 핀 활성 → 401(P1 가드)

BE iss 케이스는 라이브 서버가 없어 자기 JWKS 를 HTTP fetch 못 하므로 _get_jwks_client 를
jwks_uri 별 라우팅 mock 으로 patch 한다(Supabase 키 / BE 키를 uri 로 구분 반환). 실제 self-fetch
도달성은 Q4(엔드포인트 무인증 200)로 분리.
"""

import json
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from fastapi.testclient import TestClient
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm

from invest_note_api.auth.constants import AUTH_ROLE
from invest_note_api.config import Settings, get_settings
from invest_note_api.main import create_app
from tests.conftest import (
    TEST_EMAIL,
    TEST_SUPABASE_URL,
    TEST_USER_ID,
    _kid,
    _public_key,
)
from tests.conftest import _private_key as _supabase_private_key

SUPABASE_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"
SUPABASE_JWKS_URI = f"{TEST_SUPABASE_URL}/auth/v1/.well-known/jwks.json"

BE_ISSUER = "https://api.invest-note.example/be"
BE_AUDIENCE = "invest-note-app"
BE_KID = "be-test-key"
BE_JWKS_URI = f"{TEST_SUPABASE_URL}/auth/.well-known/jwks.json"

# BE 서명 키쌍(모듈 레벨, 1회 생성).
_be_private_key = generate_private_key(SECP256R1())
_be_private_pem = _be_private_key.private_bytes(
    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
).decode()


def _supabase_jwk() -> PyJWK:
    return PyJWK.from_dict(
        {**json.loads(ECAlgorithm.to_jwk(_public_key)), "kid": _kid, "alg": "ES256"}
    )


def _be_jwk() -> PyJWK:
    return PyJWK.from_dict(
        {
            **json.loads(ECAlgorithm.to_jwk(_be_private_key.public_key())),
            "kid": BE_KID,
            "alg": "ES256",
        }
    )


def _routing_jwks_client():
    """_get_jwks_client(uri) 를 uri 별로 라우팅하는 mock factory.

    Supabase JWKS URI → Supabase 키, BE JWKS URI → BE 키를 반환해 한 app 안에서 두 issuer
    토큰을 서로 다른 키로 검증한다.
    """

    def factory(uri: str):
        client = MagicMock()
        if uri == BE_JWKS_URI:
            client.get_signing_key_from_jwt.return_value = _be_jwk()
        else:
            client.get_signing_key_from_jwt.return_value = _supabase_jwk()
        return client

    return MagicMock(side_effect=factory)


def _be_jwt(*, iss=BE_ISSUER, aud=BE_AUDIENCE, sub=TEST_USER_ID) -> str:
    now = int(time.time())
    payload = {"sub": sub, "email": TEST_EMAIL, "aud": aud, "iat": now, "exp": now + 3600}
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(payload, _be_private_pem, algorithm="ES256", headers={"kid": BE_KID})


def _supabase_jwt(*, iss=SUPABASE_ISSUER, aud=AUTH_ROLE, sub=TEST_USER_ID) -> str:
    now = int(time.time())
    payload = {"sub": sub, "email": TEST_EMAIL, "aud": aud, "iat": now, "exp": now + 3600}
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(
        payload, _supabase_private_key, algorithm="ES256", headers={"kid": _kid}
    )


@contextmanager
def _registry_client():
    """Supabase 핀 + BE 활성 양 issuer registry 가 켜진 클라이언트."""
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        oidc_issuer=SUPABASE_ISSUER,  # Supabase iss 핀 활성(prod 시뮬레이션)
        be_token_signing_key=_be_private_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with patch(
        "invest_note_api.auth.jwt._get_jwks_client", _routing_jwks_client()
    ):
        with TestClient(app) as client:
            yield client


def test_case1_supabase_issuer_valid():
    # ① Supabase iss + 올바른 aud → 200(무회귀, P4).
    with _registry_client() as client:
        token = _supabase_jwt()
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_ID


def test_case2_be_issuer_valid():
    # ② BE iss + ES256 + BE aud → 200(BE 토큰이 registry 로 검증, P5 dormant 경로 유닛 가동).
    with _registry_client() as client:
        token = _be_jwt()
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_ID


def test_case3_unknown_issuer_rejected():
    # ③ unknown iss → 401. registry 미매칭 → Supabase default 분기 → iss 핀 불일치로 거부.
    with _registry_client() as client:
        token = _supabase_jwt(iss="https://evil.example.com/auth/v1")
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case4_supabase_iss_with_be_aud_rejected():
    # ④ Supabase iss + BE aud → 401(per-issuer aud 격리, P6).
    with _registry_client() as client:
        token = _supabase_jwt(aud=BE_AUDIENCE)
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case4b_be_iss_with_supabase_aud_rejected():
    # ④' BE iss + Supabase aud(authenticated) → 401(BE entry aud=invest-note-app 불일치).
    with _registry_client() as client:
        token = _be_jwt(aud=AUTH_ROLE)
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case5_missing_iss_rejected_when_pinned():
    # ⑤ iss 클레임 없음 + Supabase 핀 활성 → 401(MissingRequiredClaim, P1 가드).
    with _registry_client() as client:
        token = _supabase_jwt(iss=None)
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


# --- Phase 2b-1: B8 in-process 자기검증 + B9 expand 무회귀 ---


@contextmanager
def _be_active_client_no_jwks_mock():
    """BE 활성 Settings + Supabase 핀 — _get_jwks_client 를 **BE URI 에 대해 깨뜨려서**
    BE 검증이 self-fetch 를 안 함을 입증한다(B8). Supabase URI 만 정상 mock.
    """
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        oidc_issuer=SUPABASE_ISSUER,
        be_token_signing_key=_be_private_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    def factory(uri: str):
        # BE JWKS URI 로 fetch 가 일어나면 self-fetch 가 살아있다는 뜻 → 즉시 실패시킨다.
        if uri == BE_JWKS_URI:
            raise AssertionError(
                "BE 검증이 be_jwks_uri 를 self-fetch 했다 — in-process key 직접 주입 위배(B8)"
            )
        client = MagicMock()
        client.get_signing_key_from_jwt.return_value = _supabase_jwk()
        return client

    with patch("invest_note_api.auth.jwt._get_jwks_client", MagicMock(side_effect=factory)):
        with TestClient(app) as client:
            yield client


def test_b8_be_token_verified_in_process_without_self_fetch():
    # B8: BE 토큰이 self-fetch(BE_JWKS_URI) 없이 in-process public key 로 검증돼 200.
    # (factory 가 BE URI fetch 시 AssertionError 라 self-fetch 가 일어나면 500/에러로 드러난다.)
    with _be_active_client_no_jwks_mock() as client:
        token = _be_jwt()
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_ID


def test_b9_supabase_token_still_valid_when_be_active():
    # B9 (expand hard gate): BE 활성 Settings 에서도 Supabase 토큰은 여전히 200(fallback 무회귀,
    # 구 앱 lockout 0). Supabase 검증은 in-process 분기를 안 타고 기존 JWKS fetch 경로 유지.
    with _be_active_client_no_jwks_mock() as client:
        token = _supabase_jwt()
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_ID
