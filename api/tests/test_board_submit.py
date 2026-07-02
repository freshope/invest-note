"""앱 거래내역서 제보 라우터(routers/board.py) 테스트 — presign / submit 보안 불변식.

실DB 미사용: get_current_user override + R2 더미 자격증명 settings + FakePool/FakeConnection.
presign 의 R2 호출은 로컬 SigV4(네트워크 無). submit 의 FakeConnection 응답 순서는
count_recent_submissions(fetchval) → create_post(fetchrow) → create_attachment(fetchrow).
"""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.main import create_app
from invest_note_api.storage import r2

from .fake_pool import FakeConnection, FakePool

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _stub_r2_move(monkeypatch) -> None:
    """submit 의 temp→정식 copy/보상 delete 는 R2 네트워크 호출이므로 no-op 으로 막는다.
    오케스트레이션(순서·prefix·보상)만 검증 — 블로킹/threadpool 동작은 테스트 범위 밖."""
    monkeypatch.setattr(r2, "copy_object", lambda *a, **k: None)
    monkeypatch.setattr(r2, "delete_object", lambda *a, **k: None)


def _r2_settings(**over) -> Settings:
    base = dict(
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


def _key(uid=USER_ID) -> str:
    """presign 이 발급하는 temp 스테이징 key 형태(submit body 에 실린다)."""
    return f"temp/{uid}/{uuid4()}.xlsx"


def _attachment_row(storage_key: str, post_id: str) -> dict:
    return {
        "id": str(uuid4()),
        "post_id": post_id,
        "comment_id": None,
        "user_id": str(USER_ID),
        "original_name": "statement.xlsx",
        "content_type": XLSX_CT,
        "size_bytes": 2048,
        "storage_key": storage_key,
        "bucket": "statements",
        "created_at": "2026-06-22T00:00:00Z",
    }


def _post_row(post_id: str) -> dict:
    return {
        "id": post_id,
        "board_type": "broker_statement",
        "user_id": str(USER_ID),
        "title": "[unsupported_broker] 키움",
        "body": "",
        "status": "open",
        "is_pinned": False,
        "metadata": '{"type": "unsupported_broker", "broker": "\\ud0a4\\uc6c0"}',
        "created_at": "2026-06-22T00:00:00Z",
        "updated_at": "2026-06-22T00:00:00Z",
    }


def _submit_body(storage_key: str, **over) -> dict:
    body = {
        "type": "unsupported_broker",
        "broker": "키움",
        "country": "KR",
        "note": "미지원 증권사 제보",
        "consent": True,
        "attachment": {
            "storage_key": storage_key,
            "original_name": "statement.xlsx",
            "content_type": XLSX_CT,
            "size_bytes": 2048,
        },
    }
    body.update(over)
    return body


# ─────────────────────────── presign ───────────────────────────


def test_presign_returns_server_generated_key():
    """presign → storage_key 서버 생성(temp/{uid}/ prefix) + upload_url + bucket + expires_in."""
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/broker-statement/presign",
        json={"original_name": "내역.xlsx", "content_type": XLSX_CT, "size_bytes": 1024},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["storage_key"].startswith(f"temp/{USER_ID}/")
    assert body["storage_key"].endswith(".xlsx")
    assert body["bucket"] == "statements"
    assert body["expires_in"] == 900
    assert "r2.cloudflarestorage.com" in body["upload_url"]


def test_presign_rejects_bad_ext():
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/broker-statement/presign",
        json={"original_name": "내역.txt", "content_type": "text/plain", "size_bytes": 10},
    )
    assert resp.status_code == 415


def test_presign_rejects_oversize():
    client = _client(_r2_settings())
    resp = client.post(
        "/v1/board/broker-statement/presign",
        json={"original_name": "내역.xlsx", "content_type": XLSX_CT, "size_bytes": 21 * 1024 * 1024},
    )
    assert resp.status_code == 413


def test_presign_dormant_503():
    """R2 미설정이면 presign 503(dormant 무회귀)."""
    client = _client(Settings())
    resp = client.post(
        "/v1/board/broker-statement/presign",
        json={"original_name": "내역.xlsx", "content_type": XLSX_CT, "size_bytes": 1024},
    )
    assert resp.status_code == 503


# ─────────────────────────── submit 스키마 경계 ───────────────────────────


def test_submit_has_no_board_type_field():
    """board_type 주입 불가 — extra='forbid' 로 422(서버 하드코딩)."""
    client = _client(_r2_settings(), pool=FakePool())
    body = _submit_body(_key())
    body["board_type"] = "notice"
    resp = client.post("/v1/board/broker-statement", json=body)
    assert resp.status_code == 422


def test_submit_consent_false_422():
    client = _client(_r2_settings(), pool=FakePool())
    resp = client.post("/v1/board/broker-statement", json=_submit_body(_key(), consent=False))
    assert resp.status_code == 422


# ─────────────────────────── submit 보안 불변식 ───────────────────────────


def test_submit_foreign_user_key_403():
    """남 user 의 storage_key 는 403(prefix 불일치)."""
    other = uuid4()
    client = _client(_r2_settings(), pool=FakePool())
    resp = client.post(
        "/v1/board/broker-statement", json=_submit_body(_key(other))
    )
    assert resp.status_code == 403


def test_submit_rejects_bad_ext_on_register():
    client = _client(_r2_settings(), pool=FakePool())
    bad_key = f"temp/{USER_ID}/{uuid4()}.exe"
    body = _submit_body(bad_key)
    body["attachment"]["original_name"] = "malware.exe"
    body["attachment"]["content_type"] = "application/octet-stream"
    resp = client.post("/v1/board/broker-statement", json=body)
    assert resp.status_code == 415


def test_submit_rejects_oversize_on_register():
    client = _client(_r2_settings(), pool=FakePool())
    body = _submit_body(_key())
    body["attachment"]["size_bytes"] = 21 * 1024 * 1024
    resp = client.post("/v1/board/broker-statement", json=body)
    assert resp.status_code == 413


def test_submit_spam_over_limit_429():
    """기존 10건이면 11번째 제보는 429(recent>=_SPAM_MAX). count_recent_submissions → 10."""
    conn = FakeConnection(10)  # count fetchval → 기존 10건
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/broker-statement", json=_submit_body(_key()))
    assert resp.status_code == 429


def test_submit_success_201(monkeypatch):
    """정상 → 201 + {post_id, attachment}. temp→정식 copy 후 final key 로 등록.
    응답 순서: count(0) → post → attachment."""
    _stub_r2_move(monkeypatch)
    temp_key = _key()
    final_key = r2.promote_key(temp_key)
    post_id = str(uuid4())
    conn = FakeConnection(0, _post_row(post_id), _attachment_row(final_key, post_id))
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/broker-statement", json=_submit_body(temp_key))
    assert resp.status_code == 201
    body = resp.json()
    assert body["post_id"] == post_id
    # 등록 storage_key 는 정식 위치(promote 결과) — temp 가 아니다.
    assert body["attachment"]["storage_key"] == final_key
    assert body["attachment"]["storage_key"].startswith("broker_statement/")
    assert body["attachment"]["original_name"] == "statement.xlsx"


def test_submit_missing_upload_400(monkeypatch):
    """temp 객체 부재(업로드 미완료로 submit) → copy_object 가 400."""
    from invest_note_api.errors import APIError

    def _raise(*a, **k):
        raise APIError(r2.ERR_UPLOAD_MISSING, 400)

    monkeypatch.setattr(r2, "copy_object", _raise)
    conn = FakeConnection(0)  # count → 0 통과 후 copy 단계서 400
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/broker-statement", json=_submit_body(_key()))
    assert resp.status_code == 400


def test_submit_dormant_503():
    """R2 미설정이면 submit 503(presign 우회 직접 호출 방어). 스키마 통과분으로 호출."""
    client = _client(Settings(), pool=FakePool())
    resp = client.post("/v1/board/broker-statement", json=_submit_body(_key()))
    assert resp.status_code == 503


def test_submit_at_limit_passes(monkeypatch):
    """기존 9건이면 10번째 제보는 통과(10건까지 허용, 11번째부터 거부). count → 9 → 201."""
    _stub_r2_move(monkeypatch)
    temp_key = _key()
    final_key = r2.promote_key(temp_key)
    post_id = str(uuid4())
    conn = FakeConnection(9, _post_row(post_id), _attachment_row(final_key, post_id))
    client = _client(_r2_settings(), pool=FakePool(conn))
    resp = client.post("/v1/board/broker-statement", json=_submit_body(temp_key))
    assert resp.status_code == 201
