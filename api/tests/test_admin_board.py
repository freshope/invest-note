"""멀티 게시판 어드민 라우터 테스트 — require_admin 게이트 / catch-all 회귀 / CRUD / 댓글.

실DB 미사용(test_admin_crud 와 동일 전략): Settings override + mock user email 로 게이트를,
repo 호출은 FakePool/FakeConnection 으로 검증한다. metadata(jsonb)는 실 asyncpg 처럼 JSON
**문자열**로 fixture 를 구성해야 _post_row_to_dict 의 json.loads 가 dict 로 정규화한다.
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


def _make_admin_app(admin_emails: str = ADMIN_EMAILS_CSV, *, r2: bool = False):
    extra = (
        dict(
            r2_endpoint_url="https://accountid.r2.cloudflarestorage.com",
            r2_bucket="statements",
            r2_access_key_id="dummy-access-key",
            r2_secret_access_key="dummy-secret-key",
        )
        if r2
        else {}
    )
    settings = Settings(supabase_url=TEST_SUPABASE_URL, admin_emails=admin_emails, **extra)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def _client(app, *, email: str | None = ADMIN_EMAIL, admin_pool=...) -> TestClient:
    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=uuid4(), email=email, raw={})

    app.dependency_overrides[get_current_user] = mock_user
    if admin_pool is not ...:
        app.dependency_overrides[get_pool] = lambda: admin_pool
    return TestClient(app)


def _post_row(**over) -> dict:
    """board_posts row fixture — metadata 는 실 asyncpg 처럼 JSON 문자열."""
    row = {
        "id": str(uuid4()),
        "board_type": "notice",
        "user_id": None,
        "title": "공지",
        "body": "본문",
        "status": "open",
        "is_pinned": False,
        "metadata": "{}",
        "created_at": "2026-06-19T00:00:00Z",
        "updated_at": "2026-06-19T00:00:00Z",
    }
    row.update(over)
    return row


# ─────────────────────────── require_admin 게이트 ───────────────────────────


def test_boards_forbidden_for_non_allowlist():
    """allowlist 외 이메일은 403 — pool 도달 전 게이트 차단."""
    app = _make_admin_app()
    client = _client(app, email="intruder@evil.com", admin_pool=FakePool())
    assert client.get("/admin/boards").status_code == 403


# ─────────────────────────── 목록 엔벨로프 / catch-all 회귀 ───────────────────────────


def test_boards_list_envelope_shape():
    """GET /admin/boards → {items, total}. count(fetchval) 후 rows(fetch) 순서, metadata=dict."""
    app = _make_admin_app()
    row = _post_row(metadata='{"broker": "키움"}')
    conn = FakeConnection(1, [row])
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get("/admin/boards?board_type=notice&page=1&q=공지")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["metadata"] == {"broker": "키움"}


def test_boards_not_swallowed_by_catch_all():
    """/admin/boards 가 admin.py 의 /{table} catch-all 로 흡수되지 않고 board 라우터로 간다.

    catch-all 로 흡수됐다면 _TABLE_PATH 에 없는 'boards' 라 404 가 났을 것. board 라우터가
    먼저 등록돼 200 + 엔벨로프 shape 이어야 한다.
    """
    app = _make_admin_app()
    conn = FakeConnection(0, [])
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get("/admin/boards")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


# ─────────────────────────── 상세(post + comments + attachments) ───────────────────────────


def test_boards_detail_shape():
    """상세: post + comments + attachments 합본. get_post 순서 = fetchrow(post)→fetch(c)→fetch(a)."""
    app = _make_admin_app()
    post = _post_row()
    comment = {
        "id": str(uuid4()),
        "post_id": post["id"],
        "user_id": None,
        "is_admin": True,
        "body": "관리자 댓글",
        "created_at": "2026-06-19T01:00:00Z",
        "updated_at": "2026-06-19T01:00:00Z",
    }
    attachment = {
        "id": str(uuid4()),
        "post_id": post["id"],
        "comment_id": None,
        "user_id": None,
        "original_name": "statement.xlsx",
        "content_type": None,
        "size_bytes": 1024,
        "storage_key": None,
        "bucket": None,
        "created_at": "2026-06-19T02:00:00Z",
    }
    conn = FakeConnection(post, [comment], [attachment])
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get(f"/admin/boards/{post['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "공지"
    assert body["metadata"] == {}
    assert body["comments"][0]["body"] == "관리자 댓글"
    assert body["attachments"][0]["original_name"] == "statement.xlsx"


def test_boards_detail_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection(None)  # get_post fetchrow → None
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.get(f"/admin/boards/{uuid4()}").status_code == 404


# ─────────────────────────── create (201 / 검증) ───────────────────────────


def test_boards_create_201():
    app = _make_admin_app()
    created = _post_row(board_type="notice", title="새 공지")
    conn = FakeConnection(created)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.post(
        "/admin/boards",
        json={"board_type": "notice", "title": "새 공지", "body": "내용"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "새 공지"
    assert resp.json()["metadata"] == {}


def test_boards_create_rejects_invalid_board_type():
    """board_type Literal 위반은 422."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    resp = client.post("/admin/boards", json={"board_type": "unknown", "title": "x"})
    assert resp.status_code == 422


def test_boards_create_rejects_extra_field():
    """extra='forbid' — 미허용 키는 422."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    resp = client.post(
        "/admin/boards", json={"board_type": "notice", "title": "x", "status": "open"}
    )
    assert resp.status_code == 422


# ─────────────────────────── update (200 / null 거부 / 404) ───────────────────────────


def test_boards_update_200():
    app = _make_admin_app()
    updated = _post_row(status="closed", is_pinned=True)
    conn = FakeConnection(updated)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch(
        f"/admin/boards/{updated['id']}", json={"status": "closed", "is_pinned": True}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_boards_update_rejects_explicit_null():
    """NOT NULL 컬럼(title/body/status/is_pinned)에 명시적 null 은 제약위반(500) 대신 422."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    pid = str(uuid4())
    assert client.patch(f"/admin/boards/{pid}", json={"title": None}).status_code == 422
    assert client.patch(f"/admin/boards/{pid}", json={"status": None}).status_code == 422
    assert client.patch(f"/admin/boards/{pid}", json={"is_pinned": None}).status_code == 422


def test_boards_update_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection(None)  # update_post fetchrow → None
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch(f"/admin/boards/{uuid4()}", json={"status": "closed"})
    assert resp.status_code == 404


def test_boards_update_empty_body_returns_post_shape():
    """빈 PATCH(편집 키 없음)는 상세 합본이 아닌 BoardPostRow(10키)만 반환 — comments 키 없음."""
    app = _make_admin_app()
    post = _post_row()
    conn = FakeConnection(post)  # 빈 분기 fetchrow(post) → row
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.patch(f"/admin/boards/{post['id']}", json={})
    assert resp.status_code == 200
    assert "comments" not in resp.json()
    assert resp.json()["title"] == "공지"


def test_boards_invalid_uuid_path_422():
    """path param UUID 타이핑 — 잘못된 uuid 는 repo 도달 전 422(FastAPI 검증)."""
    app = _make_admin_app()
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool())
    assert client.get("/admin/boards/not-a-uuid").status_code == 422


# ─────────────────────────── delete (204 / 404) ───────────────────────────


def test_boards_delete_204():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 1")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.delete(f"/admin/boards/{uuid4()}").status_code == 204


def test_boards_delete_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 0")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.delete(f"/admin/boards/{uuid4()}").status_code == 404


# ─────────────────────────── comment create / delete ───────────────────────────


def test_comment_create_201():
    """create_comment: fetchval(post 존재=1) → fetchrow(comment row) 순서."""
    app = _make_admin_app()
    pid = str(uuid4())
    comment = {
        "id": str(uuid4()),
        "post_id": pid,
        "user_id": None,
        "is_admin": True,
        "body": "확인했습니다",
        "created_at": "2026-06-19T03:00:00Z",
        "updated_at": "2026-06-19T03:00:00Z",
    }
    conn = FakeConnection(1, comment)
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.post(f"/admin/boards/{pid}/comments", json={"body": "확인했습니다"})
    assert resp.status_code == 201
    assert resp.json()["body"] == "확인했습니다"
    assert resp.json()["is_admin"] is True


def test_comment_create_post_not_found_404():
    """없는 post 에 댓글 → 선검증 fetchval None → 404."""
    app = _make_admin_app()
    conn = FakeConnection(None)  # fetchval(post 존재?) → None
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.post(f"/admin/boards/{uuid4()}/comments", json={"body": "x"})
    assert resp.status_code == 404


def test_comment_delete_204():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 1")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.delete(f"/admin/boards/comments/{uuid4()}").status_code == 204


def test_comment_delete_not_found_404():
    app = _make_admin_app()
    conn = FakeConnection("DELETE 0")
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.delete(f"/admin/boards/comments/{uuid4()}").status_code == 404


# ─────────────────────────── 첨부 다운로드(presigned GET) ───────────────────────────


def _attachment_row(**over) -> dict:
    row = {
        "id": str(uuid4()),
        "post_id": str(uuid4()),
        "comment_id": None,
        "user_id": None,
        "original_name": "statement.xlsx",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size_bytes": 2048,
        "storage_key": "broker_statement/abc/file.xlsx",
        "bucket": "statements",
        "created_at": "2026-06-22T00:00:00Z",
    }
    row.update(over)
    return row


def test_attachment_download_forbidden_for_non_allowlist():
    """require_admin 게이트 — allowlist 외 403(pool 도달 전)."""
    app = _make_admin_app(r2=True)
    client = _client(app, email="intruder@evil.com", admin_pool=FakePool())
    assert client.get(f"/admin/boards/attachments/{uuid4()}/download").status_code == 403


def test_attachment_download_returns_presigned_url():
    """정상 → {download_url} presigned GET(attachment disposition)."""
    app = _make_admin_app(r2=True)
    conn = FakeConnection(_attachment_row())
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    resp = client.get(f"/admin/boards/attachments/{uuid4()}/download")
    assert resp.status_code == 200
    url = resp.json()["download_url"]
    assert "r2.cloudflarestorage.com" in url
    assert "X-Amz-Signature" in url


def test_attachment_download_not_found_404():
    app = _make_admin_app(r2=True)
    conn = FakeConnection(None)  # get_attachment fetchrow → None
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.get(f"/admin/boards/attachments/{uuid4()}/download").status_code == 404


def test_attachment_download_null_storage_key_404():
    """행은 있으나 storage_key 가 null(코멘트 첨부 등) → presign 불가 → 404."""
    app = _make_admin_app(r2=True)
    conn = FakeConnection(_attachment_row(storage_key=None))
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.get(f"/admin/boards/attachments/{uuid4()}/download").status_code == 404


def test_attachment_download_dormant_503():
    """R2 미설정(자격증명 없음) → generate_get_url 이 503(dormant)."""
    app = _make_admin_app(r2=False)
    conn = FakeConnection(_attachment_row())
    client = _client(app, email=ADMIN_EMAIL, admin_pool=FakePool(conn))
    assert client.get(f"/admin/boards/attachments/{uuid4()}/download").status_code == 503
