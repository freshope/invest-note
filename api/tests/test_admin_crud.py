"""어드민 패널 CRUD 테스트 — require_admin 게이트 / shape / nps CRUD.

실DB 미사용(conftest 와 동일 mock 전략): require_admin allowlist 는 Settings override +
mock user email 로, repo 호출은 FakePool/FakeConnection 으로 검증한다. RLS 제거 후 admin 은
메인 풀(owner) 로 cross-user 조회하며, 실제 cross-user 격리/조회는 실DB e2e 에서 검증.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.main import create_app

from .conftest import TEST_SUPABASE_URL
from .fake_pool import FakeConnection, FakePool

ADMIN_EMAIL = "admin@example.com"
ADMIN_EMAILS_CSV = "admin@example.com, second@example.com"


def _make_admin_app(admin_emails: str = ADMIN_EMAILS_CSV):
    """admin_emails 가 require_admin 의 Depends(get_settings) 로도 흘러가도록 override 포함.

    create_app 에 넘긴 settings 는 CORS·lifespan 용이고, 라우터의 Depends(get_settings) 는
    별도 lru_cache 함수라 같은 settings 를 보장하려면 override 해야 한다(기존 테스트 관례).
    """
    settings = Settings(supabase_url=TEST_SUPABASE_URL, admin_emails=admin_emails)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def _client(app, *, email: str | None = ADMIN_EMAIL, admin_pool=...) -> TestClient:
    """get_current_user(email override) + get_pool override 한 클라이언트.

    RLS 제거 후 admin 라우트는 메인 풀(get_pool)을 쓰므로 그 의존을 FakePool 로 override 한다.
    """

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=uuid4(), email=email, raw={})

    app.dependency_overrides[get_current_user] = mock_user
    if admin_pool is not ...:
        app.dependency_overrides[get_pool] = lambda: admin_pool
    return TestClient(app)


# ─────────────────────────── require_admin 게이트 ───────────────────────────


def test_allowlist_member_passes_gate():
    """allowlist 이메일이면 게이트 통과(stats 200). admin_pool 은 FakeConn 으로 stats 1행."""
    app = _make_admin_app()
    conn = FakeConnection({"users": 3, "accounts": 2, "trades": 5, "stocks": 9, "nps_unmatched": 1})
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get("/admin/stats")
    assert resp.status_code == 200
    assert resp.json() == {"users": 3, "accounts": 2, "trades": 5, "stocks": 9, "nps_unmatched": 1}


def test_non_allowlist_email_forbidden():
    """allowlist 외 이메일은 403 — pool 도달 전 게이트 차단."""
    app = _make_admin_app()
    client = _client(app, email="intruder@evil.com", admin_pool=FakePool())
    resp = client.get("/admin/stats")
    assert resp.status_code == 403


def test_missing_email_forbidden():
    """email 클레임 없음 → 403."""
    app = _make_admin_app()
    client = _client(app, email=None, admin_pool=FakePool())
    assert client.get("/admin/stats").status_code == 403


def test_substring_email_does_not_match():
    """substring 함정 회귀: allowlist 가 'admin@example.com' 일 때 'example.com'(부분문자열)은 403.

    raw 콤마 문자열 `in` 비교였다면 'example.com' in 'admin@example.com,...' → True 로 통과했을 것.
    set 정확비교라 거부되어야 한다.
    """
    app = _make_admin_app(admin_emails="admin@example.com")
    client = _client(app, email="example.com", admin_pool=FakePool())
    assert client.get("/admin/stats").status_code == 403


def test_email_case_insensitive_match():
    """대소문자 무시 정규화 — 'ADMIN@Example.com' 도 통과."""
    app = _make_admin_app(admin_emails="admin@example.com")
    conn = FakeConnection({"users": 0, "accounts": 0, "trades": 0, "stocks": 0, "nps_unmatched": 0})
    client = _client(app, email="ADMIN@Example.com", admin_pool=FakePool(conn))
    assert client.get("/admin/stats").status_code == 200


# ─────────────────────────── 리스트 엔벨로프 / shape ───────────────────────────


def test_list_envelope_shape():
    """GET /admin/{table} → {items, total}. count(fetchval) 후 rows(fetch) 순서."""
    app = _make_admin_app()
    uid = str(uuid4())
    conn = FakeConnection(7, [{"id": uid, "created_at": "2026-01-01T00:00:00Z"}])
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get("/admin/users?page=1&page_size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 7
    assert body["items"] == [{"id": uid, "created_at": "2026-01-01T00:00:00Z"}]


def test_list_unknown_table_404():
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    assert client.get("/admin/kis-tokens").status_code == 404


def test_list_hyphen_path_maps_to_table():
    """custom-tags 하이픈 경로가 매핑되어 200(엔벨로프)."""
    app = _make_admin_app()
    conn = FakeConnection(0, [])
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get("/admin/custom-tags")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


# ─────────────────────────── stocks 수정 화이트리스트 ───────────────────────────


def test_stock_update_rejects_unknown_field():
    """편집 화이트리스트 밖 필드(marcap_rank)는 422(extra='forbid')."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    resp = client.patch("/admin/stocks/KR/005930", json={"marcap_rank": 1})
    assert resp.status_code == 422


def test_stock_update_rejects_explicit_null():
    """NOT NULL 컬럼(asset_name/market)에 명시적 null 은 제약위반(500) 대신 422."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    assert client.patch("/admin/stocks/KR/005930", json={"asset_name": None}).status_code == 422
    assert client.patch("/admin/stocks/KR/005930", json={"market": None}).status_code == 422


def test_stock_update_returns_row():
    app = _make_admin_app()
    updated = {"country_code": "KR", "ticker": "005930", "asset_name": "삼성전자우"}
    conn = FakeConnection(updated)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch("/admin/stocks/KR/005930", json={"asset_name": "삼성전자우"})
    assert resp.status_code == 200
    assert resp.json()["asset_name"] == "삼성전자우"


def test_stock_update_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection(None)  # update_stock fetchrow → None
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch("/admin/stocks/KR/999999", json={"is_active": False})
    assert resp.status_code == 404


# ─────────────────────────── nps_unmatched CRUD ───────────────────────────


def test_nps_create_201():
    app = _make_admin_app()
    row = {
        "nps_name": "테스트종목",
        "nps_as_of": "2026-06-01",
        "holding_level": "major",
        "resolved_ticker": None,
        "created_at": "2026-06-01T00:00:00Z",
    }
    conn = FakeConnection(row)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.post(
        "/admin/nps-unmatched",
        json={"nps_name": "테스트종목", "nps_as_of": "2026-06-01", "holding_level": "major"},
    )
    assert resp.status_code == 201
    assert resp.json()["nps_name"] == "테스트종목"


def test_nps_create_conflict_409():
    """PK 충돌(on conflict do nothing → None) 시 409."""
    app = _make_admin_app()
    conn = FakeConnection(None)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.post(
        "/admin/nps-unmatched",
        json={"nps_name": "중복", "nps_as_of": "2026-06-01", "holding_level": "held"},
    )
    assert resp.status_code == 409


def test_nps_update_by_query_params():
    app = _make_admin_app()
    row = {
        "nps_name": "테스트종목",
        "nps_as_of": "2026-06-01",
        "holding_level": "major",
        "resolved_ticker": "005930",
        "created_at": "2026-06-01T00:00:00Z",
    }
    conn = FakeConnection(row)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch(
        "/admin/nps-unmatched",
        params={"nps_name": "테스트종목", "nps_as_of": "2026-06-01"},
        json={"resolved_ticker": "005930"},
    )
    assert resp.status_code == 200
    assert resp.json()["resolved_ticker"] == "005930"


def test_nps_update_rejects_explicit_null():
    """holding_level(NOT NULL)에 명시적 null 은 제약위반(500) 대신 422."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    resp = client.patch(
        "/admin/nps-unmatched",
        params={"nps_name": "테스트종목", "nps_as_of": "2026-06-01"},
        json={"holding_level": None},
    )
    assert resp.status_code == 422


def test_nps_update_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection(None)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch(
        "/admin/nps-unmatched",
        params={"nps_name": "없음", "nps_as_of": "2026-06-01"},
        json={"resolved_ticker": "005930"},
    )
    assert resp.status_code == 404


def test_nps_delete_204():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 1")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.request(
        "DELETE",
        "/admin/nps-unmatched",
        params={"nps_name": "테스트종목", "nps_as_of": "2026-06-01"},
    )
    assert resp.status_code == 204


def test_nps_delete_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 0")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.request(
        "DELETE",
        "/admin/nps-unmatched",
        params={"nps_name": "없음", "nps_as_of": "2026-06-01"},
    )
    assert resp.status_code == 404


# ─────────────────────────── admin_repo SQL 인자 직접 검증 ───────────────────────────


class _RecordingConn:
    """fetch/fetchval/fetchrow/execute 호출의 (query, args) 를 기록하는 fake."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self._idx = 0
        self.calls: list[tuple[str, tuple]] = []

    def _next(self):
        if self._idx >= len(self._responses):
            return None
        v = self._responses[self._idx]
        self._idx += 1
        return v

    async def fetchval(self, query, *args):
        self.calls.append((query, args))
        return self._next()

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        r = self._next()
        return r if r is not None else []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self._next()

    async def execute(self, query, *args):
        self.calls.append((query, args))
        r = self._next()
        return r if isinstance(r, str) else "OK"


async def test_repo_list_clamps_page_size_and_passes_q():
    """page_size>200 은 200 으로 clamp, q 는 ILIKE 패턴으로 전달."""
    from invest_note_api.db_ops import admin_repo

    conn = _RecordingConn(5, [{"name": "x"}])
    rows, total = await admin_repo.list_rows(conn, "accounts", page=2, page_size=500, q="abc")
    assert total == 5 and rows == [{"name": "x"}]
    # count 쿼리에 q 패턴이 인자로 전달
    count_query, count_args = conn.calls[0]
    assert count_args == ("%abc%",)
    assert "ilike" in count_query.lower()
    # rows 쿼리: limit=200(clamp), offset=(2-1)*200=200
    _, list_args = conn.calls[1]
    assert list_args[-2:] == (200, 200)


async def test_repo_update_stock_only_whitelisted_fields():
    """화이트리스트 밖 키는 admin_repo 단에서도 무시(SET 절에 미포함)."""
    from invest_note_api.db_ops import admin_repo

    conn = _RecordingConn({"ticker": "005930"})
    await admin_repo.update_stock(
        conn, "KR", "005930", {"asset_name": "X", "marcap_rank": 1, "ticker": "HACK"}
    )
    query, args = conn.calls[0]
    assert "asset_name" in query
    assert "marcap_rank" not in query
    # ticker 는 WHERE 식별자로만($n), SET 절엔 없음
    assert "set asset_name" in query.lower()
    assert args[0] == "X"
