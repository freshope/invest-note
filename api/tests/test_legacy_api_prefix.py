"""Legacy `/api/*` prefix alias smoke 테스트.

FE / 모바일 앱 마이그레이션 전까지 BE 는 신 경로(`/<resource>`)와 legacy 경로
(`/api/<resource>`)를 모두 지원한다. 각 라우터를 두 번 register 했으므로 두 경로가
같은 라우트로 dispatch 되는지를 대표 엔드포인트에서 확인한다.
"""
from fastapi.testclient import TestClient

from tests.conftest import TEST_EMAIL, TEST_USER_ID, make_jwt


# 비인증 호출이 401 을 반환하는 대표 경로들 — DB 없이 검증 가능.
UNAUTH_PATHS = [
    "/me",
    "/accounts",
    "/trades",
    "/portfolio/summary",
    "/portfolio/holding",
    "/stocks/search",
    "/stocks/quote",
    "/analysis/dashboard",
]


def test_legacy_prefix_unauth_status_equivalence(auth_client: TestClient) -> None:
    """모든 대표 경로에서 `/<x>` 와 `/api/<x>` 가 동일한 비인증 응답을 반환한다."""
    for path in UNAUTH_PATHS:
        new = auth_client.get(path)
        legacy = auth_client.get(f"/api{path}")
        assert new.status_code == legacy.status_code, (
            f"status mismatch: {path} → {new.status_code} vs /api{path} → {legacy.status_code}"
        )
        # 비인증 경로는 401 이어야 한다 — 404 면 라우트 등록 실패.
        assert new.status_code == 401, f"{path} expected 401, got {new.status_code}"


def test_legacy_prefix_me_authenticated_equivalence(auth_client: TestClient) -> None:
    """인증된 호출에서 `/me` 와 `/api/me` 가 동일한 status + body 를 반환한다.

    /me 는 DB 의존성이 없어 가장 단순한 dual-path smoke 가 가능하다.
    """
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    new = auth_client.get("/me", headers=headers)
    legacy = auth_client.get("/api/me", headers=headers)
    assert new.status_code == 200
    assert legacy.status_code == 200
    assert new.json() == legacy.json()
    assert new.json()["user_id"] == TEST_USER_ID
    assert new.json()["email"] == TEST_EMAIL


def test_legacy_prefix_not_in_openapi_schema(auth_client: TestClient) -> None:
    """legacy `/api/*` 경로는 OpenAPI 스키마에 노출되지 않아야 한다."""
    r = auth_client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    legacy_paths = [p for p in paths if p.startswith("/api/")]
    assert legacy_paths == [], f"legacy paths leaked to schema: {legacy_paths}"
