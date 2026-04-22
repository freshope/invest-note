from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tests.conftest import TEST_USER_ID
from tests.fake_pool import FakeConnection, make_fake_acquire

ACC_ID = uuid4()
ACC_ROW = {
    "id": ACC_ID,
    "user_id": UUID(TEST_USER_ID),
    "name": "주식계좌",
    "broker": "키움",
    "cash_balance": 1000000,
    "created_at": "2026-01-01T00:00:00+09:00",
    "updated_at": "2026-01-01T00:00:00+09:00",
}


def _patch(conn: FakeConnection):
    return patch("invest_note_api.routers.accounts.acquire_for_user", make_fake_acquire(conn))


# ─── GET /api/accounts ───────────────────────────────────────────────────────

def test_list_accounts_empty(accounts_client):
    conn = FakeConnection([], [])
    with _patch(conn):
        r = accounts_client.get("/api/accounts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_accounts_with_trade_count(accounts_client):
    conn = FakeConnection(
        [ACC_ROW],
        [{"account_id": ACC_ID, "c": 3}],
    )
    with _patch(conn):
        r = accounts_client.get("/api/accounts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "주식계좌"
    assert data[0]["trade_count"] == 3
    assert data[0]["cash_balance"] == 1000000.0


def test_list_accounts_trade_count_defaults_zero(accounts_client):
    conn = FakeConnection([ACC_ROW], [])
    with _patch(conn):
        r = accounts_client.get("/api/accounts")
    assert r.json()[0]["trade_count"] == 0


# ─── POST /api/accounts ──────────────────────────────────────────────────────

def test_create_account_success(accounts_client):
    conn = FakeConnection(ACC_ROW)
    with _patch(conn):
        r = accounts_client.post(
            "/api/accounts",
            json={"name": "주식계좌", "broker": "키움", "cash_balance": "1,000,000"},
        )
    assert r.status_code == 201
    assert r.json()["name"] == "주식계좌"


def test_create_account_empty_name(accounts_client):
    conn = FakeConnection()
    with _patch(conn):
        r = accounts_client.post("/api/accounts", json={"name": "  ", "cash_balance": 0})
    assert r.status_code == 400
    assert "error" in r.json()


def test_create_account_cash_balance_over_max(accounts_client):
    conn = FakeConnection()
    with _patch(conn):
        r = accounts_client.post(
            "/api/accounts",
            json={"name": "계좌", "cash_balance": "99999999999999999.99"},
        )
    assert r.status_code == 400
    assert "error" in r.json()


def test_create_account_broker_empty_string_becomes_null(accounts_client):
    created = {**ACC_ROW, "broker": None}
    conn = FakeConnection(created)
    with _patch(conn):
        r = accounts_client.post(
            "/api/accounts",
            json={"name": "계좌", "broker": "", "cash_balance": 0},
        )
    assert r.status_code == 201


# ─── PATCH /api/accounts/{id} ────────────────────────────────────────────────

def test_update_account_partial_success(accounts_client):
    updated = {**ACC_ROW, "broker": "미래에셋"}
    conn = FakeConnection(updated)
    with _patch(conn):
        r = accounts_client.patch(
            f"/api/accounts/{ACC_ID}",
            json={"broker": "미래에셋"},
        )
    assert r.status_code == 200
    assert r.json()["broker"] == "미래에셋"


def test_update_account_empty_body_returns_204(accounts_client):
    conn = FakeConnection()
    with _patch(conn):
        r = accounts_client.patch(f"/api/accounts/{ACC_ID}", json={})
    assert r.status_code == 204


def test_update_account_not_found(accounts_client):
    conn = FakeConnection(None)  # fetchrow returns None (RLS 차단)
    with _patch(conn):
        r = accounts_client.patch(
            f"/api/accounts/{ACC_ID}",
            json={"name": "새이름"},
        )
    assert r.status_code == 404
    assert r.json() == {"error": "계좌를 찾을 수 없습니다."}


# ─── DELETE /api/accounts/{id} ───────────────────────────────────────────────

def test_delete_account_success(accounts_client):
    conn = FakeConnection(0, "DELETE 1")
    with _patch(conn):
        r = accounts_client.delete(f"/api/accounts/{ACC_ID}")
    assert r.status_code == 204


def test_delete_account_has_trades_returns_409(accounts_client):
    conn = FakeConnection(3)  # trade_count > 0
    with _patch(conn):
        r = accounts_client.delete(f"/api/accounts/{ACC_ID}")
    assert r.status_code == 409
    assert r.json() == {"error": "거래 기록이 있는 계좌는 삭제할 수 없습니다."}


def test_delete_account_not_found(accounts_client):
    conn = FakeConnection(0, "DELETE 0")  # no trades, but DELETE hits 0 rows (RLS)
    with _patch(conn):
        r = accounts_client.delete(f"/api/accounts/{ACC_ID}")
    assert r.status_code == 404
    assert r.json() == {"error": "계좌를 찾을 수 없습니다."}


# ─── GET /api/accounts/{id}/trade-count ──────────────────────────────────────

def test_trade_count_success(accounts_client):
    conn = FakeConnection(ACC_ID, 5)  # exists check, then count
    with _patch(conn):
        r = accounts_client.get(f"/api/accounts/{ACC_ID}/trade-count")
    assert r.status_code == 200
    assert r.json() == {"count": 5}


def test_trade_count_account_not_found(accounts_client):
    conn = FakeConnection(None)  # exists check returns None
    with _patch(conn):
        r = accounts_client.get(f"/api/accounts/{ACC_ID}/trade-count")
    assert r.status_code == 404
    assert r.json() == {"error": "계좌를 찾을 수 없습니다."}


def test_trade_count_returns_zero_when_count_is_none(accounts_client):
    conn = FakeConnection(ACC_ID, None)  # exists OK, count None → 0
    with _patch(conn):
        r = accounts_client.get(f"/api/accounts/{ACC_ID}/trade-count")
    assert r.status_code == 200
    assert r.json() == {"count": 0}


# ─── 401 인증 미제공 ──────────────────────────────────────────────────────────

def test_unauthenticated_list_accounts_returns_401(client):
    """auth_client 없이 raw client로 인증 헤더 없이 요청 — 401 반환."""
    from invest_note_api.db import get_pool

    from tests.conftest import _make_app

    app = _make_app()

    async def mock_pool():
        return None

    app.dependency_overrides[get_pool] = mock_pool
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/accounts")
    assert r.status_code == 401
    assert r.json() == {"error": "Unauthorized"}


# ─── 500 엣지 케이스 ──────────────────────────────────────────────────────────

def test_create_account_db_returns_none_gives_500(accounts_client):
    conn = FakeConnection(None)  # fetchrow returns None
    with _patch(conn):
        r = accounts_client.post(
            "/api/accounts",
            json={"name": "계좌", "cash_balance": 0},
        )
    assert r.status_code == 500


# ─── 400 추가 케이스 ──────────────────────────────────────────────────────────

def test_create_account_negative_cash_balance_returns_400(accounts_client):
    conn = FakeConnection()
    with _patch(conn):
        r = accounts_client.post(
            "/api/accounts",
            json={"name": "계좌", "cash_balance": "-1"},
        )
    assert r.status_code == 400
    assert "error" in r.json()


def test_update_account_invalid_name_returns_400(accounts_client):
    conn = FakeConnection()
    with _patch(conn):
        r = accounts_client.patch(
            f"/api/accounts/{ACC_ID}",
            json={"name": "x" * 51},
        )
    assert r.status_code == 400
    assert "error" in r.json()
