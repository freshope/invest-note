"""앱 라우터 prefix alias smoke 테스트.

앱(인증) 라우터의 정식 경로는 `/v1/<resource>` 이고, bare(`/<resource>`)·legacy
(`/api/<resource>`)는 배포된 구버전 앱 호환용 숨김 alias 다. 각 라우터를 세 번
register 했으므로 세 경로가 같은 라우트로 dispatch 되는지를 대표 엔드포인트에서
확인한다.
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

# 정식 `/v1` 외 하위호환 alias prefix 들.
ALIAS_PREFIXES = ["", "/api"]


def test_prefix_unauth_status_equivalence(auth_client: TestClient) -> None:
    """모든 대표 경로에서 `/v1/<x>` 와 alias(`/<x>`, `/api/<x>`)가 동일한 비인증 응답을 반환한다."""
    for path in UNAUTH_PATHS:
        canonical = auth_client.get(f"/v1{path}")
        # 정식 경로는 401 이어야 한다 — 404 면 /v1 라우트 등록 실패.
        assert canonical.status_code == 401, f"/v1{path} expected 401, got {canonical.status_code}"
        for prefix in ALIAS_PREFIXES:
            alias = auth_client.get(f"{prefix}{path}")
            assert alias.status_code == canonical.status_code, (
                f"status mismatch: /v1{path} → {canonical.status_code} vs "
                f"{prefix}{path} → {alias.status_code}"
            )


def test_prefix_me_authenticated_equivalence(auth_client: TestClient) -> None:
    """인증된 호출에서 `/v1/me` 와 alias(`/me`, `/api/me`)가 동일한 status + body 를 반환한다.

    /me 는 DB 의존성이 없어 가장 단순한 multi-path smoke 가 가능하다.
    """
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    canonical = auth_client.get("/v1/me", headers=headers)
    assert canonical.status_code == 200
    assert canonical.json()["user_id"] == TEST_USER_ID
    assert canonical.json()["email"] == TEST_EMAIL
    for prefix in ALIAS_PREFIXES:
        alias = auth_client.get(f"{prefix}/me", headers=headers)
        assert alias.status_code == 200
        assert alias.json() == canonical.json()


def test_openapi_schema_exposes_v1_only(auth_client: TestClient) -> None:
    """앱 라우터는 정식 `/v1/*` 만 스키마에 노출되고 bare·`/api/*` alias 는 숨김이어야 한다."""
    r = auth_client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    # 정식 /v1 경로 노출 확인.
    assert "/v1/me" in paths, "canonical /v1 path missing from schema"
    # 하위호환 alias 는 숨김.
    assert "/me" not in paths, "bare app path leaked to schema"
    legacy_paths = [p for p in paths if p.startswith("/api/")]
    assert legacy_paths == [], f"legacy paths leaked to schema: {legacy_paths}"
