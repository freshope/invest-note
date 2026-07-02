import time
from datetime import datetime, timezone
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

TEST_USER_ID = str(uuid4())


def dt(s: str) -> datetime:
    """ISO 문자열 → UTC datetime."""
    return datetime.fromisoformat(s).astimezone(timezone.utc)
TEST_EMAIL = "test@example.com"

# 테스트 Settings 가 개발 머신 api/.env.local 값(provider 토글·실제 키)에 오염되지 않게
# dotenv 소스를 전역 비활성화한다 — 명시 kwargs 로 안 넘긴 필드가 .env.local 로 덮여
# 로컬에서만 실패하는 테스트(CI 는 .env.local 없음)를 막는다.
from invest_note_api.config import Settings as _Settings  # noqa: E402

_Settings.model_config["env_file"] = None

# 테스트용 EC 키쌍 (세션당 1회 생성). 미등록(non-registry) issuer/foreign-key 음성 케이스용.
_private_key = generate_private_key(SECP256R1())
_public_key = _private_key.public_key()
_kid = "test-key-id"

# BE issuer 토큰 발급용 키/설정(2c: Supabase fallback 제거 후 유일한 통과 경로).
# make_jwt 가 이 키로 서명한 BE 토큰을 발급하고, auth_client 가 동일 signing key 를 Settings 에
# 실어 registry BE entry(in-process verify_key)로 검증한다.
BE_ISSUER = "https://api.invest-note.example/be"
BE_AUDIENCE = "invest-note-app"
BE_KID = "be-test-key"
_be_private_key = generate_private_key(SECP256R1())
_be_private_pem = _be_private_key.private_bytes(
    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
).decode()


def make_jwt(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    expires_delta: int = 3600,
    iss: str | None = BE_ISSUER,
    aud: str = BE_AUDIENCE,
) -> str:
    """BE issuer 토큰 발급(ES256, BE signing key). auth_client registry 로 검증되는 유효 토큰.

    iss=None 으로 호출하면 iss 클레임 없는 토큰(2c: registry 미매칭 → 401 음성 케이스).
    """
    payload = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_delta,
    }
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(
        payload, _be_private_pem, algorithm="ES256", headers={"kid": BE_KID}
    )


def _make_app():
    from invest_note_api.config import Settings
    from invest_note_api.main import create_app

    settings = Settings()
    return create_app(settings)


def _be_settings():
    """BE issuer registry 가 활성화된 Settings — 실제 토큰 검증 경로 테스트용(auth_client)."""
    from invest_note_api.config import Settings

    return Settings(
        be_token_signing_key=_be_private_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
    )


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
    `app.state.fx_cache` 가 초기화되어야 라우터의 dependency 해석이 성공한다.
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
    """실제 JWT 검증을 수행하는 클라이언트 — 401 케이스 + 유효 BE 토큰 200 테스트에 사용.

    BE issuer registry 활성(_be_settings) → make_jwt 가 발급한 BE 토큰이 in-process verify_key
    로 검증된다. 2c fallback 제거로 registry 미등록 토큰(non-BE iss·iss 누락)은 전원 401.
    """
    from invest_note_api.config import get_settings
    from invest_note_api.main import create_app

    settings = _be_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
