import time

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_EMAIL, TEST_USER_ID, _kid, _private_key, make_jwt


def test_me_no_header(auth_client: TestClient) -> None:
    r = auth_client.get("/me")
    assert r.status_code == 401


def test_me_invalid_token(auth_client: TestClient) -> None:
    r = auth_client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_me_expired_token(auth_client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": TEST_USER_ID,
            "email": TEST_EMAIL,
            "aud": "authenticated",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
        },
        _private_key,
        algorithm="ES256",
        headers={"kid": _kid},
    )
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_me_valid_token(auth_client: TestClient) -> None:
    token = make_jwt()
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] == TEST_EMAIL
