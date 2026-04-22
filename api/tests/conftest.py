import json
import time
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

TEST_USER_ID = str(uuid4())
TEST_EMAIL = "test@example.com"
TEST_SUPABASE_URL = "https://test.supabase.co"

# 테스트용 EC 키쌍 (세션당 1회 생성)
_private_key = generate_private_key(SECP256R1())
_public_key = _private_key.public_key()
_kid = "test-key-id"
_jwks = {
    "keys": [
        {**json.loads(ECAlgorithm.to_jwk(_public_key)), "kid": _kid, "alg": "ES256", "use": "sig"}
    ]
}


def make_jwt(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    expires_delta: int = 3600,
) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_delta,
    }
    return jwt.encode(payload, _private_key, algorithm="ES256", headers={"kid": _kid})


def _make_app():
    from invest_note_api.config import Settings
    from invest_note_api.main import create_app

    settings = Settings(supabase_url=TEST_SUPABASE_URL)
    return create_app(settings)


@pytest.fixture
def client() -> TestClient:
    """인증이 override된 클라이언트 — 대부분의 엔드포인트 테스트에 사용."""
    from invest_note_api.auth.dependency import get_current_user
    from invest_note_api.auth.jwt import AuthenticatedUser

    app = _make_app()

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=UUID(TEST_USER_ID), email=TEST_EMAIL, raw={})

    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


@pytest.fixture
def auth_client():
    """실제 JWT 검증을 수행하는 클라이언트 — 401 케이스 테스트에 사용."""
    app = _make_app()

    # PyJWKClient의 fetch_data를 테스트용 JWKS로 교체
    with patch.object(jwt.PyJWKClient, "fetch_data", return_value=_jwks):
        with TestClient(app) as c:
            yield c
