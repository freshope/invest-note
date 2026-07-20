"""import preview/commit HTTP 엔드포인트 테스트 — Fake harness 기반.

/import/preview·/import/commit 의 HTTP 계약을 검증한다. preview 는 가드(415/400) +
happy-path(캡처 위임→ticker 해결→카운트), commit 은 가드(원장 미존재 400)까지 커버한다.
commit 의 전체 INSERT/merge 경로는 group·pnl mock 표면이 커 실DB 테스트
(test_trade_import_commit_realdb.py) 담당 — 여기서는 소스(원장) 가드까지만.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from invest_note_api.broker_import.base import ParsedTrade, ParseResult
from invest_note_api.routers import trades as trades_module
from invest_note_api.services.broker_capture import CaptureResult
from tests.conftest import TEST_EMAIL, TEST_USER_ID, _make_app
from tests.fake_pool import FakeConnection, make_fake_acquire, make_fake_pool


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

    def test_happy_path_captures_resolves_counts(self, client, monkeypatch):
        """캡처 2행(1 해결·1 미해결) → new_count=1·unresolved=1·error=1, staging_id=batch_id."""
        batch_id = str(uuid4())

        async def fake_capture(
            pool, settings, *, user_id, broker_key, filename, content_type, file_bytes
        ):
            pr = ParseResult(
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
            return CaptureResult(
                batch_id=batch_id,
                is_new_file=True,
                row_count=2,
                trade_row_count=2,
                parse_result=pr,
            )

        monkeypatch.setattr(
            "invest_note_api.routers.trades.capture_statement", fake_capture
        )

        async def fake_resolve(resolve_items, ticker_hints, *, conn, isins, openfigi_api_key):
            # 삼성전자만 해결, "없는종목" 은 미해결로 남긴다.
            return {("KR", "삼성전자"): {"code": "005930", "exchange": ""}}

        monkeypatch.setattr(
            "invest_note_api.routers.trades.resolve_tickers", fake_resolve
        )
        # 중복판정 date-range fetch(list_trades)는 acquire_for_user 경로 — 기존거래 없음(→[]).
        monkeypatch.setattr(
            "invest_note_api.routers.trades.acquire_for_user",
            make_fake_acquire(FakeConnection()),
        )

        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("toss.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "toss_pdf"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["new_count"] == 1
        assert data["duplicate_count"] == 0
        assert data["unresolved_ticker_count"] == 1
        assert data["error_count"] == 1
        # staging_id 필드에 batch_id 가 실린다(원장 durable, TTL staging 없음).
        assert data["staging_id"] == batch_id

    def test_new_account_none_ignores_cross_account_dup(self, client, monkeypatch):
        """account_id 미지정(신규 계좌 예정) preview 는 다른 계좌의 동일거래를 dup 으로 세지 않는다.

        회귀 가드: dup 을 cross-account 로 근사하면 dup_count 가 new_count(=staged-dup)를 깎아
        신규 등록 수가 commit(빈 계좌 → dup 0·insert 1)보다 적게 나온다. 검증은 계좌 스코프여야
        하며 신규 계좌는 빈 상태이므로 dup 0 이어야 한다.
        """
        from tests.test_trades import _make_trade_row, _to_record

        batch_id = str(uuid4())

        async def fake_capture(pool, settings, *, user_id, broker_key, filename, content_type, file_bytes):
            pr = ParseResult(trades=[
                ParsedTrade(source_row_no=1, traded_at_kst="2024-01-10", trade_type="BUY",
                            asset_name="삼성전자", quantity=10, price=70000, country_code="KR"),
            ])
            return CaptureResult(batch_id=batch_id, is_new_file=True, row_count=1,
                                 trade_row_count=1, parse_result=pr)

        async def fake_resolve(resolve_items, ticker_hints, *, conn, isins, openfigi_api_key):
            return {("KR", "삼성전자"): {"code": "005930", "exchange": ""}}

        # 다른 계좌("other-acct")에 preview 종목과 완전히 동일한 시그니처의 거래가 있어도,
        # account_id 없는 preview 라면 fetch 되면 안 된다(계좌 스코프). fetch 되면 dup=1 로 회귀.
        matching = _to_record(_make_trade_row(
            id_="other", account_id="other-acct", ticker="005930", asset_name="삼성전자",
            trade_type="BUY", quantity=10, price=70000,
        ))
        monkeypatch.setattr("invest_note_api.routers.trades.capture_statement", fake_capture)
        monkeypatch.setattr("invest_note_api.routers.trades.resolve_tickers", fake_resolve)
        monkeypatch.setattr("invest_note_api.routers.trades.acquire_for_user",
                            make_fake_acquire(FakeConnection([matching])))

        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("kt.xls", b"<html></html>", "application/vnd.ms-excel")},
            params={"broker_key": "koreainvest_xls"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["new_count"] == 1
        assert data["duplicate_count"] == 0  # cross-account 거래는 신규 계좌 dup 으로 세지 않음
        assert data["excluded_count"] == 0

    def test_parser_raises_broker_mismatch_400(self, client, monkeypatch):
        """선택 증권사 파서가 다른 형식 파일에 raise(예: xlsx 파서 ← PDF) → 500 아닌 400 안내."""

        class RaisingParser:
            display_name = "삼성증권"
            version = "1"

            def parse(self, file_bytes, filename):
                raise ValueError("File is not a zip file")

        monkeypatch.setitem(trades_module.PARSERS, "toss_pdf", RaisingParser())
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("wrong.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "toss_pdf"},
        )
        assert resp.status_code == 400, resp.text
        assert "삼성증권" in resp.json()["error"]

    def test_empty_parse_broker_mismatch_400(self, client, monkeypatch):
        """거래·계좌번호·에러 모두 없는 빈 결과(다른 증권사 PDF) → 조용한 0건 대신 400 안내."""

        class EmptyParser:
            display_name = "토스증권"
            version = "1"

            def parse(self, file_bytes, filename):
                return ParseResult()

        monkeypatch.setitem(trades_module.PARSERS, "toss_pdf", EmptyParser())
        resp = client.post(
            "/v1/trades/import/preview",
            files={"file": ("other.pdf", b"%PDF-1.4", "application/pdf")},
            params={"broker_key": "toss_pdf"},
        )
        assert resp.status_code == 400, resp.text
        assert "토스증권" in resp.json()["error"]


class TestImportCommit:
    def test_batch_not_found_400(self, client, monkeypatch):
        """원장에 batch 거래 행이 없으면(미존재/타 user/만료 파일) 400. user 격리는 WHERE user_id."""

        async def fake_ledger_rows(conn, *, batch_id, user_id):
            return []

        monkeypatch.setattr(
            "invest_note_api.routers.trades.get_ledger_trade_rows", fake_ledger_rows
        )
        resp = client.post(
            "/v1/trades/import/commit",
            json={"staging_id": str(uuid4()), "account_id": "a1"},
        )
        assert resp.status_code == 400

    def test_malformed_batch_id_400(self, client):
        resp = client.post(
            "/v1/trades/import/commit",
            json={"staging_id": "not-a-uuid", "account_id": "a1"},
        )
        assert resp.status_code == 400
