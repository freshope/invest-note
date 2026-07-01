"""import preview/commit HTTP 엔드포인트 테스트 — Fake harness 기반.

기존 test_trades.py 가 다루지 않던 /import/preview·/import/commit 의 HTTP 계약을 검증한다.
preview 는 가드(415/400) + happy-path(파싱→ticker 해결→staging), commit 은 가드(만료 400·
타 user 403)까지 커버한다. commit 의 전체 INSERT/merge 경로는 group·pnl mock 표면이 커
별도(테스트 DB 또는 추가 mock) — 여기서는 staging 가드까지만.
"""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from invest_note_api.broker_import.base import ParsedTrade, ParseResult
from invest_note_api.routers import trades as trades_module
from tests.conftest import TEST_EMAIL, TEST_USER_ID, _make_app
from tests.fake_pool import FakeConnection, make_fake_acquire, make_fake_pool


@pytest.fixture
def staging_store(monkeypatch):
    """import staging(DB repo)을 in-memory dict 로 대체 (pool 은 fake 라 실제 DB 불가)."""
    store: dict[str, dict] = {}

    async def fake_put(conn, staging_id, user_id, payload, expires_at):
        store[staging_id] = {"user_id": user_id, **payload}

    async def fake_get(conn, staging_id):
        return store.get(staging_id)

    async def fake_delete(conn, staging_id):
        store.pop(staging_id, None)

    monkeypatch.setattr("invest_note_api.routers.trades.put_import_staging", fake_put)
    monkeypatch.setattr("invest_note_api.routers.trades.get_import_staging", fake_get)
    monkeypatch.setattr("invest_note_api.routers.trades.delete_import_staging", fake_delete)
    return store


@pytest.fixture
def client():
    """인증 + fake pool(plain acquire) override 클라이언트."""
    from invest_note_api.auth.dependency import get_current_user
    from invest_note_api.auth.jwt import AuthenticatedUser
    from invest_note_api.db import get_pool

    app = _make_app()

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=UUID(TEST_USER_ID), email=TEST_EMAIL, raw={})

    async def mock_pool():
        return make_fake_pool(FakeConnection())

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_pool] = mock_pool
    with TestClient(app) as c:
        yield c


class TestImportPreview:
    def test_unsupported_extension_415(self, client):
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("a.txt", b"x", "text/plain")},
            params={"broker_key": "toss_pdf"},
        )
        assert resp.status_code == 415

    def test_unknown_broker_400(self, client):
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "does_not_exist"},
        )
        assert resp.status_code == 400

    def test_missing_broker_400(self, client):
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_happy_path_parses_resolves_stages(self, client, staging_store, monkeypatch):
        """파싱 2행(1 해결·1 미해결) → new_count=1·unresolved=1·error=1, staging 1건 영속."""

        class FakeParser:
            display_name = "토스증권"

            def parse(self, file_bytes, filename):
                return ParseResult(
                    trades=[
                        ParsedTrade(
                            source_row_no=1,
                            traded_at_kst="2024-01-10",
                            trade_type="BUY",
                            asset_name="삼성전자",
                            quantity=10,
                            price=70000,
                            country_code="KR",
                        ),
                        ParsedTrade(
                            source_row_no=2,
                            traded_at_kst="2024-01-11",
                            trade_type="BUY",
                            asset_name="없는종목",
                            quantity=1,
                            price=1000,
                            country_code="KR",
                        ),
                    ]
                )

        monkeypatch.setitem(trades_module.PARSERS, "fake_broker", FakeParser())

        async def fake_resolve(resolve_items, ticker_hints, *, conn, isins, openfigi_api_key):
            # 삼성전자만 해결, "없는종목" 은 미해결로 남긴다.
            return {("KR", "삼성전자"): {"code": "005930", "exchange": ""}}

        monkeypatch.setattr(
            "invest_note_api.routers.trades.resolve_tickers", fake_resolve
        )
        # list_trades(중복판정)·staging put 은 acquire_for_user 경로 — 기존거래 없음(fetch→[]).
        monkeypatch.setattr(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(FakeConnection()),
        )

        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("toss.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "fake_broker"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["broker_name"] == "토스증권"
        assert data["new_count"] == 1
        assert data["duplicate_count"] == 0
        assert data["unresolved_ticker_count"] == 1
        assert data["error_count"] == 1
        assert data["staging_id"]
        # staging 영속 + rows 에 해결된 1건만 들어간다.
        assert len(staging_store) == 1
        staged = next(iter(staging_store.values()))
        assert len(staged["rows"]) == 1
        assert staged["rows"][0]["ticker_symbol"] == "005930"

    def test_parser_raises_broker_mismatch_400(self, client, monkeypatch):
        """선택 증권사 파서가 다른 형식 파일에 raise(예: xlsx 파서 ← PDF) → 500 아닌 400 안내."""

        class RaisingParser:
            display_name = "삼성증권"

            def parse(self, file_bytes, filename):
                raise ValueError("File is not a zip file")

        monkeypatch.setitem(trades_module.PARSERS, "fake_broker", RaisingParser())
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("wrong.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "fake_broker"},
        )
        assert resp.status_code == 400, resp.text
        assert "삼성증권" in resp.json()["error"]

    def test_empty_parse_broker_mismatch_400(self, client, monkeypatch):
        """거래·계좌번호·에러 모두 없는 빈 결과(다른 증권사 PDF) → 조용한 0건 대신 400 안내."""

        class EmptyParser:
            display_name = "토스증권"

            def parse(self, file_bytes, filename):
                return ParseResult()

        monkeypatch.setitem(trades_module.PARSERS, "fake_broker", EmptyParser())
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("other.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "fake_broker"},
        )
        assert resp.status_code == 400, resp.text
        assert "토스증권" in resp.json()["error"]


class TestImportCommit:
    def test_expired_staging_400(self, client, staging_store, monkeypatch):
        monkeypatch.setattr(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(FakeConnection()),
        )
        resp = client.post(
            "/v1/trades/import/commit",
            json={"staging_id": "nonexistent", "account_id": "a1"},
        )
        assert resp.status_code == 400

    def test_wrong_user_403(self, client, staging_store, monkeypatch):
        monkeypatch.setattr(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(FakeConnection()),
        )
        # 다른 사용자의 staging — 토큰 user 와 불일치라 403.
        staging_store["sid-other"] = {
            "user_id": "00000000-0000-0000-0000-0000000000ff",
            "rows": [],
            "usd_skip_count": 0,
        }
        resp = client.post(
            "/v1/trades/import/commit",
            json={"staging_id": "sid-other", "account_id": "a1"},
        )
        assert resp.status_code == 403
