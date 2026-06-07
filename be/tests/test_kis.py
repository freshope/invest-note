"""external.kis 토큰 캐시 + 요청 헬퍼 검증."""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from invest_note_api.config import Settings
from invest_note_api.external import kis
from invest_note_api.external.constants import KIS_MOCK_BASE_URL, KIS_REAL_BASE_URL

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


# ---- 레이트리밋 페이싱 (실측 2건/초, EGW00201) ----


async def test_acquire_rate_slot_blocks_third_call_then_releases(monkeypatch):
    monkeypatch.setattr(kis, "_RATE_WINDOW_SECONDS", 0.15)
    state = _state()
    t0 = time.monotonic()
    assert await kis._acquire_rate_slot(state, None) is True
    assert await kis._acquire_rate_slot(state, None) is True
    assert await kis._acquire_rate_slot(state, None) is True  # 윈도우 경과 후 획득
    assert time.monotonic() - t0 >= 0.13  # 3번째는 윈도우만큼 대기


async def test_acquire_rate_slot_budget_exhausted_returns_false():
    state = _state()
    now = time.monotonic()
    state.recent_calls.extend([now, now])  # 윈도우 꽉 참
    assert await kis._acquire_rate_slot(state, 0.0) is False


async def test_kis_get_throttle_budget_gives_up_without_request():
    """슬롯 부족 + 짧은 budget → API 호출 없이 None (시세 경로의 빠른 fallback)."""
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
