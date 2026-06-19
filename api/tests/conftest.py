import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from fastapi.testclient import TestClient
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm

from invest_note_api.auth.constants import AUTH_ROLE

TEST_USER_ID = str(uuid4())


def dt(s: str) -> datetime:
    """ISO 문자열 → UTC datetime."""
    return datetime.fromisoformat(s).astimezone(timezone.utc)
TEST_EMAIL = "test@example.com"
TEST_SUPABASE_URL = "https://test.supabase.co"
TEST_JWKS_URI = f"{TEST_SUPABASE_URL}/auth/v1/.well-known/jwks.json"

# 테스트 Settings 가 개발 머신 api/.env.local 값(provider 토글·실제 키)에 오염되지 않게
# dotenv 소스를 전역 비활성화한다 — 명시 kwargs 로 안 넘긴 필드가 .env.local 로 덮여
# 로컬에서만 실패하는 테스트(CI 는 .env.local 없음)를 막는다. get_settings() 경로의
# 필수 SUPABASE_URL 은 CI(ci-api.yml env)와 동일하게 env 로 공급한다.
from invest_note_api.config import Settings as _Settings  # noqa: E402

_Settings.model_config["env_file"] = None
os.environ.setdefault("SUPABASE_URL", TEST_SUPABASE_URL)

# 테스트용 EC 키쌍 (세션당 1회 생성)
_private_key = generate_private_key(SECP256R1())
_public_key = _private_key.public_key()
_kid = "test-key-id"


def _make_mock_jwks_client() -> MagicMock:
    """네트워크 없이 테스트 키로 서명 검증하는 mock PyJWKClient."""
    signing_key = PyJWK.from_dict(
        {**json.loads(ECAlgorithm.to_jwk(_public_key)), "kid": _kid, "alg": "ES256"}
    )
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = signing_key
    # _get_jwks_client(uri) 호출 형태이므로 callable로 감쌈
    return MagicMock(return_value=mock_client)


def make_jwt(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    expires_delta: int = 3600,
    iss: str | None = None,
) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "aud": AUTH_ROLE,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_delta,
    }
    if iss is not None:
        payload["iss"] = iss
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
def accounts_client() -> TestClient:
    """인증 + pool이 override된 클라이언트 — accounts 엔드포인트 테스트용.

    acquire_for_user는 각 테스트에서 직접 patch한다.
    """
    from invest_note_api.auth.dependency import get_current_user
    from invest_note_api.auth.jwt import AuthenticatedUser
    from invest_note_api.db import get_pool

    app = _make_app()

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=UUID(TEST_USER_ID), email=TEST_EMAIL, raw={})

    async def mock_pool() -> None:
        return None

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_pool] = mock_pool
    return TestClient(app)


@pytest.fixture
def trades_client():
    """인증 + pool이 override된 클라이언트 — trades/portfolio/stocks 엔드포인트 테스트용.

    `with TestClient(...)` 으로 진입해 lifespan 을 트리거한다 — `app.state.quote_cache` /
    `app.state.trade_staging` 가 초기화되어야 라우터의 dependency 해석이 성공한다.
    """
    from invest_note_api.auth.dependency import get_current_user
    from invest_note_api.auth.jwt import AuthenticatedUser
    from invest_note_api.db import get_pool

    app = _make_app()

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=UUID(TEST_USER_ID), email=TEST_EMAIL, raw={})

    async def mock_pool() -> None:
        return None

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_pool] = mock_pool
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client():
    """실제 JWT 검증을 수행하는 클라이언트 — 401 케이스 테스트에 사용."""
    from invest_note_api.auth.jwt import _get_jwks_client

    app = _make_app()

    with patch("invest_note_api.auth.jwt._get_jwks_client", _make_mock_jwks_client()):
        with TestClient(app) as c:
            yield c

    _get_jwks_client.cache_clear()
