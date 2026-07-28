"""알림 라우터(routers/notifications.py) 테스트 — /v1/notifications* A/B/C/D.

실DB 미사용: get_current_user override + FakePool/FakeConnection(test_board 미러).
FakeConnection 응답은 호출 순서대로 소비된다:
  - A list: fetchval(total) → fetch(rows).
  - B unread-count: fetchval(count).
  - C read: fetchval(id or None).
  - D read-all: execute(mark_all_read) → execute(set_notices_seen_at) — 둘 다 no-op.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.main import create_app

from .fake_pool import FakeConnection, FakePool

USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _client(*, pool=...) -> TestClient:
    settings = Settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_ID, email="u@example.com", raw={})

    app.dependency_overrides[get_current_user] = mock_user
    if pool is not ...:
        app.dependency_overrides[get_pool] = lambda: pool
    return TestClient(app)


def _feed_row(**over) -> dict:
    row = {
        "id": str(uuid4()),
        "source": "notification",
        "type": "board_reply",
        "title": "거래내역서 제보",
        "body": "확인했습니다",
        "board_type": "broker_statement",
        "ref_id": str(uuid4()),
        "created_at": "2026-07-22T00:00:00Z",
        "read": False,
    }
    row.update(over)
    return row


# ─────────────────────────── A: 목록 ───────────────────────────


def test_list_envelope_shape():
    """GET /v1/notifications → {items, total, page}. fetchval(total)→fetch(rows) 순서."""
    notif = _feed_row(source="notification")
    notice = _feed_row(
        source="notice", type="notice", board_type="notice", body=None, read=True
    )
    conn = FakeConnection(2, [notif, notice])
    client = _client(pool=FakePool(conn))
    resp = client.get("/v1/notifications?page=1&page_size=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert [i["source"] for i in body["items"]] == ["notification", "notice"]
    assert body["items"][1]["board_type"] == "notice"
    assert body["items"][1]["body"] is None


def test_list_empty():
    conn = FakeConnection(0, [])
    client = _client(pool=FakePool(conn))
    resp = client.get("/v1/notifications")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 1}


# ─────────────────────────── B: unread-count ───────────────────────────


def test_unread_count():
    conn = FakeConnection(4)
    client = _client(pool=FakePool(conn))
    resp = client.get("/v1/notifications/unread-count")
    assert resp.status_code == 200
    assert resp.json() == {"count": 4}


# ─────────────────────────── C: 개별 읽음 ───────────────────────────


def test_mark_read_204():
    """소유·존재 → UPDATE RETURNING id → 204."""
    conn = FakeConnection(uuid4())
    client = _client(pool=FakePool(conn))
    resp = client.post(f"/v1/notifications/{uuid4()}/read")
    assert resp.status_code == 204


def test_mark_read_not_found_404():
    """없음/타인 → RETURNING None → 404."""
    conn = FakeConnection(None)
    client = _client(pool=FakePool(conn))
    resp = client.post(f"/v1/notifications/{uuid4()}/read")
    assert resp.status_code == 404


def test_mark_read_invalid_uuid_422():
    """path param UUID 타이핑 — 잘못된 uuid 는 repo 도달 전 422."""
    client = _client(pool=FakePool())
    assert client.post("/v1/notifications/not-a-uuid/read").status_code == 422


# ─────────────────────────── D: 전체 읽음 ───────────────────────────


def test_read_all_204():
    """notifications read + notices_seen upsert(한 트랜잭션) → 204."""
    conn = FakeConnection()  # 두 execute 모두 no-op
    client = _client(pool=FakePool(conn))
    resp = client.post("/v1/notifications/read-all")
    assert resp.status_code == 204


def test_read_all_not_swallowed_by_id_route():
    """/read-all 이 /{notification_id}/read 로 오라우팅되지 않고 read-all 핸들러로 간다."""
    conn = FakeConnection()
    client = _client(pool=FakePool(conn))
    # read-all 은 세그먼트 1개(POST), /{id}/read 는 2개 — 충돌 없음. 204 여야 한다.
    assert client.post("/v1/notifications/read-all").status_code == 204
