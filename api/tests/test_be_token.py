"""Phase 2a — BE 토큰 ES256 서명/JWKS 서빙 round-trip 테스트.

mint_be_token → build_be_jwks 의 public key 로 검증이 성립하는지(비대칭, P5)와
dormant(빈 키) 안전, JWKS 엔드포인트 무인증 접근(P8)을 검증한다.
"""

from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from fastapi.testclient import TestClient
from jwt import PyJWK

from invest_note_api.auth.be_token import build_be_jwks, mint_be_token
from invest_note_api.config import Settings, get_settings
from invest_note_api.main import create_app

TEST_SUPABASE_URL = "https://test.supabase.co"
BE_ISSUER = "https://api.invest-note.example/be"
BE_AUDIENCE = "invest-note-app"
BE_KID = "be-test-key"


def _ec_private_pem() -> str:
    key = generate_private_key(SECP256R1())
    return key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode()


def _be_settings() -> Settings:
    return Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_token_signing_key=_ec_private_pem(),
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
    )


def test_mint_and_verify_round_trip():
    # mint_be_token → build_be_jwks 의 public JWK 로 직접 검증(순수 crypto, mock 불필요).
    settings = _be_settings()
    sub = uuid4()
    token = mint_be_token(sub, "user@example.com", settings=settings)

    jwks = build_be_jwks(settings)
    assert len(jwks["keys"]) == 1
    public_jwk = PyJWK.from_dict(jwks["keys"][0])

    payload = jwt.decode(
        token,
        public_jwk.key,
        algorithms=["ES256"],
        audience=BE_AUDIENCE,
        issuer=BE_ISSUER,
    )
    assert payload["sub"] == str(sub)
    assert payload["email"] == "user@example.com"
    assert payload["iss"] == BE_ISSUER
    assert payload["aud"] == BE_AUDIENCE


def test_token_header_kid_matches_jwks():
    # header.kid 가 JWKS 항목 kid 와 일치해야 verifier 가 올바른 키를 고른다.
    settings = _be_settings()
    token = mint_be_token(uuid4(), None, settings=settings)
    header = jwt.get_unverified_header(token)
    jwks = build_be_jwks(settings)
    assert header["kid"] == BE_KID
    assert jwks["keys"][0]["kid"] == BE_KID


def test_mint_rejected_when_signing_key_empty():
    # dormant(빈 signing key) — 발급 시도는 명확히 거부(실수 발급 방지).
    settings = Settings(supabase_url=TEST_SUPABASE_URL)
    with pytest.raises(RuntimeError):
        mint_be_token(uuid4(), None, settings=settings)


def test_build_jwks_empty_when_dormant():
    # 빈 signing key → 빈 keys(404 아님). dormant 안전.
    settings = Settings(supabase_url=TEST_SUPABASE_URL)
    assert build_be_jwks(settings) == {"keys": []}


def test_jwks_endpoint_public_no_auth():
    # JWKS 엔드포인트는 무인증 접근 200(P8). BE 가 자기 토큰 검증 시 자기 JWKS 를
    # 인증 없이 가져올 수 있어야 순환하지 않는다.
    settings = _be_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    r = client.get("/auth/.well-known/jwks.json")  # Authorization 헤더 없음
    assert r.status_code == 200
    body = r.json()
    assert body["keys"][0]["kid"] == BE_KID
    assert body["keys"][0]["alg"] == "ES256"


def test_jwks_endpoint_empty_when_dormant():
    # dormant 시 엔드포인트도 빈 keys 200 — Supabase 경로 무영향.
    settings = Settings(supabase_url=TEST_SUPABASE_URL)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    r = client.get("/auth/.well-known/jwks.json")
    assert r.status_code == 200
    assert r.json() == {"keys": []}
