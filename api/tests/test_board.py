"""앱 게시판 라우터(routers/board.py) 사용자 엔드포인트 테스트 — notices/feedback/bug-report.

실DB 미사용: get_current_user override + FakePool/FakeConnection(test_board_submit 미러).
FakeConnection 응답은 호출 순서대로 소비된다:
  - notices 목록: list_posts = fetchval(count) → fetch(rows).
  - notices 상세: get_post = fetchrow(post) → fetch(comments) → fetch(attachments).
  - feedback/bug-report: _check_spam = fetchval(count) → create_post = fetchrow → (첨부 시) create_attachment = fetchrow.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.main import create_app
from invest_note_api.storage import r2

from .conftest import TEST_SUPABASE_URL
from .fake_pool import FakeConnection, FakePool

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
PNG_CT = "image/png"


def _r2_settings(**over) -> Settings:
    base = dict(
        supabase_url=TEST_SUPABASE_URL,
        r2_endpoint_url="https://accountid.r2.cloudflarestorage.com",
        r2_bucket="statements",
        r2_access_key_id="dummy-access-key",
        r2_secret_access_key="dummy-secret-key",
    )
    base.update(over)
    return Settings(**base)


def _client(settings: Settings, *, pool=...) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_ID, email="u@example.com", raw={})

    app.dependency_overrides[get_current_user] = mock_user
    if pool is not ...:
        app.dependency_overrides[get_pool] = lambda: pool
    return TestClient(app)


def _stub_r2_move(monkeypatch) -> None:
    monkeypatch.setattr(r2, "copy_object", lambda *a, **k: None)
    monkeypatch.setattr(r2, "delete_object", lambda *a, **k: None)


def _img_key(uid=USER_ID) -> str:
    return f"temp/{uid}/{uuid4()}.png"


def _notice_row(post_id: str, *, board_type: str = "notice", **over) -> dict:
    """board_posts row — get_post 가 fetchrow 로 반환하는 raw 형태(metadata 는 jsonb str)."""
    row = {
        "id": post_id,
        "board_type": board_type,
        "user_id": str(uuid4()),  # admin 작성자 — 상세 응답에 노출되면 안 됨
        "title": "점검 공지",
        "body": "내일 02:00 점검합니다.",
        "status": "open",
        "is_pinned": True,
        "metadata": '{"source": "admin"}',
        "created_at": "2026-06-25T00:00:00Z",
        "updated_at": "2026-06-25T00:00:00Z",
    }
    row.update(over)
    return row


def _post_row(post_id: str, board_type: str) -> dict:
    """create_post 가 fetchrow 로 반환하는 row."""
    return {
        "id": post_id,
        "board_type": board_type,
        "user_id": str(USER_ID),
        "title": f"[{board_type}]",
        "body": "본문",
        "status": "open",
        "is_pinned": False,
        "metadata": '{"source": "app"}',
        "created_at": "2026-06-25T00:00:00Z",
        "updated_at": "2026-06-25T00:00:00Z",
    }


def _attachment_row(storage_key: str, post_id: str) -> dict:
    return {
        "id": str(uuid4()),
        "post_id": post_id,
        "comment_id": None,
        "user_id": str(USER_ID),
        "original_name": "shot.png",
        "content_type": PNG_CT,
        "size_bytes": 4096,
        "storage_key": storage_key,
        "bucket": "statements",
        "created_at": "2026-06-25T00:00:00Z",
    }


# ─────────────────────────── notices 목록 ───────────────────────────


def test_list_notices_returns_items_total_page():
    """목록 → {items, total, page}. count(fetchval) → rows(fetch) 순서."""
    post_id = str(uuid4())
    conn = FakeConnection(1, [_notice_row(post_id)])
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.get("/v1/board/notices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == post_id
    assert item["is_pinned"] is True
    # 화이트리스트: 정확히 4키(D-2). admin user_id / body / status / board_type 미노출.
    assert set(item.keys()) == {"id", "title", "created_at", "is_pinned"}
    assert "user_id" not in item
    assert "body" not in item


# ─────────────────────────── notices 상세 ───────────────────────────


def test_get_notice_whitelist_fields_only():
    """상세 → 화이트리스트 6키만. user_id/comments/attachments/status/board_type 미노출."""
    post_id = str(uuid4())
    # get_post: fetchrow(post) → fetch(comments) → fetch(attachments)
    conn = FakeConnection(_notice_row(post_id), [], [])
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.get(f"/v1/board/notices/{post_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"id", "title", "body", "created_at", "is_pinned", "metadata"}
    assert "user_id" not in body
    assert "comments" not in body
    assert "attachments" not in body
    assert "board_type" not in body
    assert body["metadata"] == {"source": "admin"}


def test_get_notice_wrong_board_type_404():
    """board_type!='notice' 인 글을 공지 경로로 조회 → 404(우회 차단)."""
    post_id = str(uuid4())
    conn = FakeConnection(_notice_row(post_id, board_type="feedback"), [], [])
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.get(f"/v1/board/notices/{post_id}")
    assert resp.status_code == 404


def test_get_notice_missing_404():
    """없는 post → 404. get_post 의 fetchrow 가 None."""
    conn = FakeConnection(None)
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.get(f"/v1/board/notices/{uuid4()}")
    assert resp.status_code == 404


# ─────────────────────────── feedback ───────────────────────────


def test_submit_feedback_201():
    """의견 → 201 + {post_id}. count(0) → create_post 순서."""
    post_id = str(uuid4())
    conn = FakeConnection(0, _post_row(post_id, "feedback"))
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/feedback", json={"body": "좋아요"})
    assert resp.status_code == 201
    assert resp.json()["post_id"] == post_id


def test_submit_feedback_rejects_board_type_422():
    """board_type 주입 불가 — extra='forbid' 422(서버 하드코딩)."""
    client = _client(_r2_settings(), pool=FakePool())
    resp = client.post("/v1/board/feedback", json={"body": "x", "board_type": "notice"})
    assert resp.status_code == 422


def test_submit_feedback_spam_429():
    """최근 1시간 10건이면 429. count → 10."""
    conn = FakeConnection(10)
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/feedback", json={"body": "x"})
    assert resp.status_code == 429


# ─────────────────────────── bug-report presign ───────────────────────────


def test_bug_report_presign_image_key():
    """presign → 이미지 temp key + upload_url + bucket + expires_in."""
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/bug-report/presign",
        json={"original_name": "스샷.png", "content_type": PNG_CT, "size_bytes": 1024},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["storage_key"].startswith(f"temp/{USER_ID}/")
    assert body["storage_key"].endswith(".png")
    assert body["bucket"] == "statements"


def test_bug_report_presign_rejects_non_image_415():
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/bug-report/presign",
        json={"original_name": "내역.xlsx", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert resp.status_code == 415


def test_bug_report_presign_rejects_oversize_413():
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/bug-report/presign",
        json={"original_name": "스샷.png", "content_type": PNG_CT, "size_bytes": 11 * 1024 * 1024},
    )
    assert resp.status_code == 413


# ─────────────────────────── bug-report submit ───────────────────────────


def test_submit_bug_report_no_attachment_201():
    """첨부 없음 → 201 + {post_id, attachments:[]}. count(0) → create_post."""
    post_id = str(uuid4())
    conn = FakeConnection(0, _post_row(post_id, "bug_report"))
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/bug-report", json={"body": "버튼 안 눌림"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["post_id"] == post_id
    assert body["attachments"] == []


def test_submit_bug_report_with_attachment_promotes(monkeypatch):
    """첨부 1장 → temp→bug_report copy 후 정식 key 로 등록. count(0) → post → attachment."""
    _stub_r2_move(monkeypatch)
    temp_key = _img_key()
    final_key = r2.promote_key(temp_key, r2.BUG_REPORT_PREFIX)
    post_id = str(uuid4())
    conn = FakeConnection(
        0, _post_row(post_id, "bug_report"), _attachment_row(final_key, post_id)
    )
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post(
        "/v1/board/bug-report",
        json={
            "body": "스샷 첨부",
            "attachments": [
                {
                    "storage_key": temp_key,
                    "original_name": "shot.png",
                    "content_type": PNG_CT,
                    "size_bytes": 4096,
                }
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["post_id"] == post_id
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["storage_key"] == final_key
    assert body["attachments"][0]["storage_key"].startswith("bug_report/")


def test_submit_bug_report_multiple_attachments_promotes(monkeypatch):
    """첨부 2장 → 각각 temp→bug_report copy 후 등록. count → post → attachment×2."""
    _stub_r2_move(monkeypatch)
    temp1, temp2 = _img_key(), _img_key()
    final1 = r2.promote_key(temp1, r2.BUG_REPORT_PREFIX)
    final2 = r2.promote_key(temp2, r2.BUG_REPORT_PREFIX)
    post_id = str(uuid4())
    conn = FakeConnection(
        0,
        _post_row(post_id, "bug_report"),
        _attachment_row(final1, post_id),
        _attachment_row(final2, post_id),
    )
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post(
        "/v1/board/bug-report",
        json={
            "body": "스샷 2장",
            "attachments": [
                {
                    "storage_key": temp1,
                    "original_name": "a.png",
                    "content_type": PNG_CT,
                    "size_bytes": 4096,
                },
                {
                    "storage_key": temp2,
                    "original_name": "b.png",
                    "content_type": PNG_CT,
                    "size_bytes": 8192,
                },
            ],
        },
    )
    assert resp.status_code == 201
    keys = [a["storage_key"] for a in resp.json()["attachments"]]
    assert keys == [final1, final2]


def test_submit_bug_report_copy_failure_compensates_only_copied(monkeypatch):
    """copy 루프 2번째 장 실패 → 이미 승격된 1번 장만 보상 삭제(고아 누수 방지)."""
    temp1, temp2 = _img_key(), _img_key()
    final1 = r2.promote_key(temp1, r2.BUG_REPORT_PREFIX)
    deleted: list[str] = []
    calls = {"n": 0}

    def fake_copy(_settings, _src, _dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("R2 일시 오류")

    monkeypatch.setattr(r2, "copy_object", fake_copy)
    monkeypatch.setattr(r2, "delete_object", lambda _s, key: deleted.append(key))

    # _check_spam 의 count(0)만 소비, copy 단계에서 실패해 트랜잭션 미도달.
    client = _client(_r2_settings(), pool=FakePool(FakeConnection(0)))
    body = {
        "body": "스샷 2장",
        "attachments": [
            {"storage_key": temp1, "original_name": "a.png", "content_type": PNG_CT, "size_bytes": 4096},
            {"storage_key": temp2, "original_name": "b.png", "content_type": PNG_CT, "size_bytes": 4096},
        ],
    }
    with pytest.raises(RuntimeError):
        client.post("/v1/board/bug-report", json=body)
    assert deleted == [final1]


def test_submit_bug_report_duplicate_storage_key_400():
    """동일 storage_key 중복 첨부 → 400(promote/copy 전 차단)."""
    client = _client(_r2_settings(), pool=FakePool())
    att = {
        "storage_key": _img_key(),
        "original_name": "a.png",
        "content_type": PNG_CT,
        "size_bytes": 4096,
    }
    resp = client.post(
        "/v1/board/bug-report", json={"body": "x", "attachments": [att, dict(att)]}
    )
    assert resp.status_code == 400


def test_submit_bug_report_too_many_attachments_422():
    """첨부 6장 → 스키마 max_length(5) 초과로 422(DB 도달 전)."""
    client = _client(_r2_settings(), pool=FakePool())
    atts = [
        {
            "storage_key": _img_key(),
            "original_name": f"{i}.png",
            "content_type": PNG_CT,
            "size_bytes": 1024,
        }
        for i in range(6)
    ]
    resp = client.post("/v1/board/bug-report", json={"body": "x", "attachments": atts})
    assert resp.status_code == 422


def test_submit_bug_report_foreign_key_403():
    """남 user 의 temp key → 403(prefix 불일치). spam/copy 전에 차단."""
    other = uuid4()
    client = _client(_r2_settings(), pool=FakePool())
    resp = client.post(
        "/v1/board/bug-report",
        json={
            "body": "x",
            "attachments": [
                {
                    "storage_key": _img_key(other),
                    "original_name": "shot.png",
                    "content_type": PNG_CT,
                    "size_bytes": 4096,
                }
            ],
        },
    )
    assert resp.status_code == 403


def test_submit_bug_report_rejects_board_type_422():
    """board_type 주입 불가 — 422."""
    client = _client(_r2_settings(), pool=FakePool())
    resp = client.post("/v1/board/bug-report", json={"body": "x", "board_type": "notice"})
    assert resp.status_code == 422


def test_submit_bug_report_non_image_attachment_415():
    """첨부가 이미지가 아니면 415(prefix 통과 후 _validate_image)."""
    client = _client(_r2_settings(), pool=FakePool())
    bad_key = f"temp/{USER_ID}/{uuid4()}.xlsx"
    resp = client.post(
        "/v1/board/bug-report",
        json={
            "body": "x",
            "attachments": [
                {
                    "storage_key": bad_key,
                    "original_name": "doc.xlsx",
                    "content_type": "application/octet-stream",
                    "size_bytes": 1024,
                }
            ],
        },
    )
    assert resp.status_code == 415
