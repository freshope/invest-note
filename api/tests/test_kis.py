"""external.kis 토큰 캐시 + 요청 헬퍼 검증."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from invest_note_api.config import Settings
from invest_note_api.external import kis
from invest_note_api.external.constants import KIS_MOCK_BASE_URL, KIS_REAL_BASE_URL
from tests.fake_pool import FakeConnection, make_fake_pool

TEST_SUPABASE_URL = "https://test.supabase.co"

TOKEN_JSON = {"access_token": "tok-1", "expires_in": 86400, "token_type": "Bearer"}


def _settings(**kw) -> Settings:
    return Settings(
        supabase_url=TEST_SUPABASE_URL, kis_app_key="key", kis_app_secret="secret", **kw
    )


def _state() -> kis.KisState:
    return kis.KisState(app_key="key", app_secret="secret")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _token_handler(counter: list[int], token_json: dict | None = None):
    """tokenP 호출 횟수를 세는 handler. 그 외 경로는 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == kis.KIS_TOKEN_PATH:
            counter.append(1)
            return httpx.Response(200, json=token_json or TOKEN_JSON)
        return httpx.Response(404)

    return handler


def test_configure_kis_sets_base_url_by_env():
    state = kis.configure_kis(_settings())
    assert state.base_url == KIS_REAL_BASE_URL
    state = kis.configure_kis(_settings(kis_env="mock"))
    assert state.base_url == KIS_MOCK_BASE_URL
    # configure 는 모듈 싱글톤도 갱신한다 (lifespan 진입점).
    assert kis.is_kis_configured()
    # 키 미설정으로 복원 — .env.local 의 실제 키가 새어들지 않게 명시적으로 빈 값 전달.
    kis.configure_kis(
        Settings(supabase_url=TEST_SUPABASE_URL, kis_app_key="", kis_app_secret="")
    )
    assert not kis.is_kis_configured()


async def test_get_access_token_unconfigured_returns_none_without_network():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("미설정 상태에서 네트워크 호출 금지")

    async with _client(handler) as client:
        assert await kis.get_access_token(client, kis.KisState()) is None


async def test_get_access_token_issues_once_and_caches():
    calls: list[int] = []
    state = _state()
    async with _client(_token_handler(calls)) as client:
        first = await kis.get_access_token(client, state)
        second = await kis.get_access_token(client, state)
    assert first == second == "tok-1"
    assert len(calls) == 1


async def test_get_access_token_concurrent_calls_issue_once():
    """발급 1분당 1회 제한(EGW00133) — 동시 호출이 중복 발급하면 안 된다."""
    calls: list[int] = []
    state = _state()
    async with _client(_token_handler(calls)) as client:
        results = await asyncio.gather(*[kis.get_access_token(client, state) for _ in range(5)])
    assert all(r == "tok-1" for r in results)
    assert len(calls) == 1


async def test_get_access_token_reissues_after_expiry():
    calls: list[int] = []
    state = _state()
    async with _client(_token_handler(calls)) as client:
        await kis.get_access_token(client, state)
        state.token_expires_at = time.time() - 1  # 만료 시뮬레이션
        token = await kis.get_access_token(client, state)
    assert token == "tok-1"
    assert len(calls) == 2


async def test_get_access_token_issue_failure_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error_code": "EGW00133", "error_description": "throttle"})

    state = _state()
    async with _client(handler) as client:
        assert await kis.get_access_token(client, state) is None


async def test_issue_failure_cooldown_suppresses_retry_storm():
    """발급 실패 후 쿨다운(60s) 내 요청은 tokenP 를 재호출하지 않는다(EGW00133 연타 방지)."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403, json={"error_code": "EGW00133"})

    state = _state()
    async with _client(handler) as client:
        assert await kis.get_access_token(client, state) is None
        assert await kis.get_access_token(client, state) is None
        # 쿨다운 경과 시뮬레이션 — 재시도 재개.
        state.token_issue_failed_at = time.time() - 61
        assert await kis.get_access_token(client, state) is None
    assert len(calls) == 2


async def test_issue_cooldown_does_not_block_db_token_pickup():
    """발급 쿨다운 중에도 DB 토큰 재사용 경로는 동작 — 타 프로세스 발급분을 즉시 픽업."""
    calls: list[int] = []
    state = _db_state(InMemoryTokenConn(_db_row()))
    state.token_issue_failed_at = time.time()  # 직전 발급 실패 상태
    async with _client(_token_handler(calls)) as client:
        token = await kis.get_access_token(client, state)
    assert token == "tok-db"
    assert calls == []


async def test_kis_get_success_returns_body_and_sends_headers():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == kis.KIS_TOKEN_PATH:
            return httpx.Response(200, json=TOKEN_JSON)
        seen["headers"] = request.headers
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"rt_cd": "0", "output": {"stck_prpr": "71000"}})

    state = _state()
    async with _client(handler) as client:
        body = await kis.kis_get(
            client,
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"},
            state=state,
        )
    assert body is not None
    assert body["output"]["stck_prpr"] == "71000"
    assert seen["headers"]["authorization"] == "Bearer tok-1"
    assert seen["headers"]["appkey"] == "key"
    assert seen["headers"]["tr_id"] == "FHKST01010100"
    assert seen["headers"]["custtype"] == "P"
    assert seen["params"] == {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}


@pytest.mark.parametrize(
    "api_response",
    [
        httpx.Response(200, json={"rt_cd": "1", "msg_cd": "EGW00121", "msg1": "유효하지 않은 token"}),
        httpx.Response(500, text="server error"),
        httpx.ConnectTimeout("timeout"),
    ],
)
async def test_kis_get_failure_returns_none(api_response):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == kis.KIS_TOKEN_PATH:
            return httpx.Response(200, json=TOKEN_JSON)
        if isinstance(api_response, Exception):
            raise api_response
        return api_response

    state = _state()
    async with _client(handler) as client:
        body = await kis.kis_get(client, "/uapi/test", tr_id="FHKST01010100", params={}, state=state)
    assert body is None


async def test_kis_get_unconfigured_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("미설정 상태에서 네트워크 호출 금지")

    async with _client(handler) as client:
        assert (
            await kis.kis_get(client, "/uapi/test", tr_id="X", params={}, state=kis.KisState())
            is None
        )


# ---- 레이트리밋 페이싱 (윈도우 메커니즘, EGW00201) ----
# 운영 페이싱은 18건/초지만, 윈도우 메커니즘 검증은 한도를 2로 고정해 단순화한다.


async def test_acquire_rate_slot_blocks_third_call_then_releases(monkeypatch):
    monkeypatch.setattr(kis, "_RATE_WINDOW_SECONDS", 0.15)
    monkeypatch.setattr(kis, "_RATE_MAX_CALLS", 2)
    state = _state()
    t0 = time.monotonic()
    assert await kis._acquire_rate_slot(state, None) is True
    assert await kis._acquire_rate_slot(state, None) is True
    assert await kis._acquire_rate_slot(state, None) is True  # 윈도우 경과 후 획득
    assert time.monotonic() - t0 >= 0.13  # 3번째는 윈도우만큼 대기


async def test_acquire_rate_slot_budget_exhausted_returns_false(monkeypatch):
    monkeypatch.setattr(kis, "_RATE_MAX_CALLS", 2)
    state = _state()
    now = time.monotonic()
    state.recent_calls.extend([now, now])  # 윈도우 꽉 참
    assert await kis._acquire_rate_slot(state, 0.0) is False


async def test_kis_get_throttle_budget_gives_up_without_request(monkeypatch):
    """슬롯 부족 + 짧은 budget → API 호출 없이 None (시세 경로의 빠른 fallback)."""
    monkeypatch.setattr(kis, "_RATE_MAX_CALLS", 2)
    api_calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        api_calls.append(1)
        return httpx.Response(200, json={"rt_cd": "0"})

    state = _state()
    state.token = "tok"
    state.token_expires_at = time.time() + 86400  # 토큰 캐시 hit — 발급 호출 없음
    state.recent_calls.extend([time.monotonic(), time.monotonic()])

    async with _client(handler) as client:
        body = await kis.kis_get(
            client, "/uapi/test", tr_id="X", params={}, state=state, throttle_budget=0.0
        )
    assert body is None
    assert api_calls == []


async def test_kis_get_retries_once_on_egw00201(monkeypatch):
    monkeypatch.setattr(kis, "_RATE_RETRY_SLEEP_SECONDS", 0.0)
    api_calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == kis.KIS_TOKEN_PATH:
            return httpx.Response(200, json=TOKEN_JSON)
        api_calls.append(1)
        if len(api_calls) == 1:
            return httpx.Response(500, json={"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초과"})
        return httpx.Response(200, json={"rt_cd": "0", "output": {"stck_prpr": "71000"}})

    state = _state()
    async with _client(handler) as client:
        body = await kis.kis_get(
            client, "/uapi/test", tr_id="FHKST01010100", params={}, state=state
        )
    assert body is not None and body["output"]["stck_prpr"] == "71000"
    assert len(api_calls) == 2


# ---- 토큰 DB 영속화 (kis_tokens, 1일 1토큰 정책) ----


def _db_row(token: str = "tok-db", hours: float = 12) -> dict:
    return {
        "access_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=hours),
    }


class InMemoryTokenConn(FakeConnection):
    """kis_tokens 1행을 흉내 내는 stateful fake — upsert 가 row 에 반영된다."""

    def __init__(self, row: dict | None = None) -> None:
        super().__init__()
        self.row = row

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return self.row

    async def execute(self, query: str, *args: Any) -> str:
        if not self._is_internal(query) and "kis_tokens" in query:
            _scope, token, expires_at = args
            self.row = {"access_token": token, "expires_at": expires_at}
        return "OK"


def _db_state(conn: FakeConnection) -> kis.KisState:
    return kis.KisState(app_key="key", app_secret="secret", pool=make_fake_pool(conn))


async def test_issue_lock_sets_lock_timeout():
    """stuck holder 가 요청 경로를 무기한 블록하지 않도록 락 획득 전에 상한을 둔다."""
    from invest_note_api.external import kis_token_store

    queries: list[str] = []

    class RecordingConn(FakeConnection):
        async def execute(self, query: str, *args: Any) -> str:
            queries.append(query)
            return await super().execute(query, *args)

        async def fetchval(self, query: str, *args: Any) -> Any:
            queries.append(query)
            return await super().fetchval(query, *args)

    async with kis_token_store.issue_lock(make_fake_pool(RecordingConn())):
        pass
    lock_idx = next(i for i, q in enumerate(queries) if "pg_advisory_xact_lock" in q)
    assert any("lock_timeout" in q for q in queries[:lock_idx])


async def test_get_access_token_reuses_db_token_without_issuing():
    """DB 에 유효 토큰이 있으면 발급 호출 없이 재사용 (재시작 직후 시나리오)."""
    calls: list[int] = []
    state = _db_state(InMemoryTokenConn(_db_row()))
    async with _client(_token_handler(calls)) as client:
        token = await kis.get_access_token(client, state)
    assert token == "tok-db"
    assert calls == []


async def test_get_access_token_issues_and_persists_when_db_empty():
    """DB 미스 → 발급 1회 + upsert. 이후 새 프로세스(KisState)는 DB 토큰을 재사용."""
    calls: list[int] = []
    conn = InMemoryTokenConn()
    async with _client(_token_handler(calls)) as client:
        token = await kis.get_access_token(client, _db_state(conn))
        assert token == "tok-1"
        assert conn.row is not None and conn.row["access_token"] == "tok-1"
        # 재시작 시뮬레이션 — 같은 DB, 새 메모리 상태 → 재발급 없음.
        token2 = await kis.get_access_token(client, _db_state(conn))
    assert token2 == "tok-1"
    assert len(calls) == 1


async def test_get_access_token_double_check_picks_up_peer_token():
    """락 대기 중 타 프로세스가 발급한 경우 — load_in 재조회로 픽업, 발급 0회."""
    calls: list[int] = []
    # 1차 load 는 미스(None), 락 내 재조회는 hit — 순서 응답으로 시뮬레이션.
    conn = FakeConnection(None, _db_row("tok-peer"))
    state = _db_state(conn)
    async with _client(_token_handler(calls)) as client:
        token = await kis.get_access_token(client, state)
    assert token == "tok-peer"
    assert calls == []


async def test_get_access_token_db_stale_token_reissued():
    """DB 토큰이 만료 임박이면 재발급 + upsert 로 교체."""
    calls: list[int] = []
    conn = InMemoryTokenConn(_db_row("tok-old", hours=0.05))  # 마진(10분) 이내
    async with _client(_token_handler(calls)) as client:
        token = await kis.get_access_token(client, _db_state(conn))
    assert token == "tok-1"
    assert len(calls) == 1
    assert conn.row["access_token"] == "tok-1"
