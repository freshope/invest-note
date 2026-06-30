"""issuer registry 검증 통합 테스트 (2c: Supabase fallback 제거 후).

decode_oidc_jwt 는 registry 에 등록된 issuer(현재 BE issuer)만 통과시키고 나머지는 401 이다.
Supabase default fallback·JWKS HTTP fetch 경로는 2c 에서 제거됐다 — BE 토큰은 in-process
verify_key(_registry_with_be_key 주입)로 검증되므로 self-fetch mock 이 필요 없다.

케이스:
  ① BE iss + BE aud + BE 키 서명 → 200(registry 검증)
  ② unknown iss → 401(fallback 제거 — Supabase 검증으로 새지 않음)
  ③ iss 클레임 없음 → 401(registry 미매칭)
  ④ BE iss + 잘못된 aud → 401(per-issuer aud 격리)
  ⑤ 불변식 역전: registry 빈(BE dormant) Settings → 모든 토큰 401
"""

import time
from contextlib import contextmanager

import jwt
from fastapi.testclient import TestClient

from invest_note_api.config import Settings, get_settings
from invest_note_api.main import create_app
from tests.conftest import (
    BE_AUDIENCE,
    BE_ISSUER,
    BE_KID,
    TEST_EMAIL,
    TEST_SUPABASE_URL,
    TEST_USER_ID,
    _be_private_pem,
    _be_settings,
)


def _be_jwt(*, iss=BE_ISSUER, aud=BE_AUDIENCE, sub=TEST_USER_ID) -> str:
    now = int(time.time())
    payload = {"sub": sub, "email": TEST_EMAIL, "aud": aud, "iat": now, "exp": now + 3600}
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(payload, _be_private_pem, algorithm="ES256", headers={"kid": BE_KID})


@contextmanager
def _registry_client():
    """BE issuer registry 활성 클라이언트(in-process verify_key)."""
    settings = _be_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client


@contextmanager
def _dormant_client():
    """BE 토큰 미활성(signing key 없음) → registry 빈. 2c 불변식 역전: 전원 401."""
    settings = Settings(supabase_url=TEST_SUPABASE_URL)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client


def test_case1_be_issuer_valid():
    # ① BE iss + BE aud + BE 키 → 200(registry 가 in-process verify_key 로 검증).
    with _registry_client() as client:
        token = _be_jwt()
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_ID


def test_case2_unknown_issuer_rejected():
    # ② unknown iss → 401. fallback 제거 — Supabase 검증으로 새지 않고 iss 게이트에서 거부.
    with _registry_client() as client:
        token = _be_jwt(iss="https://evil.example.com/auth/v1")
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case3_missing_issuer_rejected():
    # ③ iss 클레임 없음 → 401(registry 미매칭). 2c 전엔 Supabase default 로 흘렀음.
    with _registry_client() as client:
        token = _be_jwt(iss=None)
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case4_be_iss_with_wrong_aud_rejected():
    # ④ BE iss + Supabase 컨벤션 aud(authenticated) → 401(per-issuer aud 격리, iss 게이트 통과 후).
    with _registry_client() as client:
        token = _be_jwt(aud="authenticated")
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_case5_dormant_registry_rejects_all():
    # ⑤ 불변식 역전(2c): registry 빈(BE dormant) → 유효 서명 BE 토큰조차 401.
    # be_token_signing_key 미설정 시 dev/test 인증 전멸 — 이 동작을 명시적으로 가드한다.
    with _dormant_client() as client:
        token = _be_jwt()
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
