"""KIS Open API(한국투자증권) 공통 클라이언트 — 토큰 캐시 + 레이트리밋 페이싱 + 요청 헬퍼.

토큰(`POST /oauth2/tokenP`, 유효 ~24h)은 in-process 캐시가 1차이고, pool 이 설정되면
kis_tokens 테이블에 영속화한다(1일 1토큰 정책 — 재시작/멀티 프로세스에서 토큰 공유).
발급은 1분당 1회 제한(EGW00133)이 있어 asyncio.Lock(프로세스 내) +
pg_advisory_xact_lock(프로세스 간, kis_token_store.issue_lock)으로 중복 발급을 차단한다.
pool=None(테스트/DB 미연결)이면 종전대로 메모리 전용으로 동작한다.

레이트리밋: 공식 기본 유량 18건/초(실전, 계좌=앱키 단위). 2026-06-07 실측 2건/초는
신규 고객 3일 제한(신청 후 3일간 3건/초) 구간 측정이었고, 2026-06-14 재실측(발급
7일 경과)에서 동시 20건 무탈락 확인 → 기본 유량 복귀. EGW00201("초당 거래건수 초과").
모든 KIS 호출(토큰 발급 포함)은 전역 슬라이딩 윈도우 리미터의 슬롯을 얻고 나간다.

시세성 TR(FHK*)은 실전/모의 tr_id 가 동일 — KIS_ENV 는 도메인 분기에만 쓴다.
(T↔V tr_id prefix 분기는 주문/계좌 TR 전용으로 이번 범위 밖.)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

from invest_note_api.config import Settings
from invest_note_api.external import kis_token_store
from invest_note_api.external.constants import (
    HTTP_TIMEOUT_SECONDS,
    KIS_MOCK_BASE_URL,
    KIS_REAL_BASE_URL,
)

logger = logging.getLogger(__name__)

KIS_TOKEN_PATH = "/oauth2/tokenP"

# 만료(expires_in, 보통 86400s) 임박 시 조기 재발급하는 여유 마진.
_TOKEN_REFRESH_MARGIN_SECONDS = 600.0

# 발급 실패 후 재시도 억제 — KIS 가 발급을 1분당 1회로 제한(EGW00133)하므로, 자격증명
# 오설정/장애 시 들어오는 요청마다 tokenP 를 때리지 않게 한다. DB 토큰 재사용 경로는
# 이 쿨다운과 무관하게 매 호출 동작한다(타 프로세스가 발급한 토큰은 즉시 픽업).
_ISSUE_FAILURE_COOLDOWN_SECONDS = 60.0

# 레이트리밋 페이싱 — 공식 기본 유량 18건/초(2026-06-14 재실측 ≥20 무탈락, 보수적 18 적용)에
# 윈도우 여유(1.05s)를 둬 서버 측 측정 jitter 흡수. ⚠️ per-process 페이서 — 한도는 계좌(앱키)
# 단위라 멀티 replica 면 합산 초과(공유 리미터 필요). 현재 replica=1 전제.
_RATE_MAX_CALLS = 18
_RATE_WINDOW_SECONDS = 1.05
# EGW00201 수신 시 1회 재시도 전 대기.
_RATE_RETRY_SLEEP_SECONDS = 0.6


@dataclass
class KisState:
    """KIS 자격증명 + 토큰 캐시 + 레이트리밋 상태. 모듈 싱글톤(_state)은 configure_kis 로 초기화."""

    app_key: str = ""
    app_secret: str = ""
    base_url: str = KIS_REAL_BASE_URL
    token: str | None = None
    token_expires_at: float = 0.0  # epoch seconds
    token_issue_failed_at: float = 0.0  # epoch seconds — 마지막 발급 실패 시각(쿨다운 기준)
    pool: Any | None = None  # asyncpg.Pool — None 이면 메모리 전용(영속화 생략)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    rate_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    recent_calls: deque[float] = field(default_factory=deque)  # monotonic timestamps


_state = KisState()


def configure_kis(settings: Settings, pool: Any | None = None) -> KisState:
    """앱 lifespan/batch 진입점에서 호출 — 자격증명 설정 + 토큰 캐시 리셋."""
    global _state
    _state = KisState(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        base_url=KIS_MOCK_BASE_URL if settings.kis_env == "mock" else KIS_REAL_BASE_URL,
        pool=pool,
    )
    return _state


def is_kis_configured(state: KisState | None = None) -> bool:
    s = state if state is not None else _state
    return bool(s.app_key and s.app_secret)


async def _acquire_rate_slot(state: KisState, max_wait: float | None) -> bool:
    """전역 슬라이딩 윈도우(2건/1.05s) 슬롯 획득. max_wait 내 확보 불가 전망이면 False.

    max_wait=None 은 무제한 대기(배치 경로). 시세 경로는 짧은 예산을 줘 슬롯이 없으면
    빠르게 포기하고 다음 공급자로 fallback 하게 한다(전체 fetch deadline 보호).
    """
    deadline = None if max_wait is None else time.monotonic() + max_wait
    while True:
        async with state.rate_lock:
            now = time.monotonic()
            while state.recent_calls and now - state.recent_calls[0] > _RATE_WINDOW_SECONDS:
                state.recent_calls.popleft()
            if len(state.recent_calls) < _RATE_MAX_CALLS:
                state.recent_calls.append(now)
                return True
            wait = _RATE_WINDOW_SECONDS - (now - state.recent_calls[0]) + 0.02
        if deadline is not None and time.monotonic() + wait > deadline:
            return False
        await asyncio.sleep(wait)


def _safe_json(res: httpx.Response) -> dict:
    try:
        data = res.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _issue_token(client: httpx.AsyncClient, state: KisState) -> None:
    """토큰 발급 시도 — 성공 시 state 에 반영, 실패 시 로그만 남긴다(호출측이 None 처리).

    직전 실패 후 쿨다운(60s) 내에는 발급을 건너뛴다 — 발급 1분당 1회 제한(EGW00133)
    하에서 실패 상태의 요청들이 tokenP 를 연타하는 것을 막는다.
    """
    if time.time() - state.token_issue_failed_at < _ISSUE_FAILURE_COOLDOWN_SECONDS:
        return
    await _acquire_rate_slot(state, None)  # 토큰 발급도 초당 건수에 포함
    try:
        res = await client.post(
            state.base_url + KIS_TOKEN_PATH,
            json={
                "grant_type": "client_credentials",
                "appkey": state.app_key,
                "appsecret": state.app_secret,
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except Exception:
        state.token_issue_failed_at = time.time()
        raise
    data = _safe_json(res) if res.status_code == 200 else {}
    token = data.get("access_token")
    if not token:
        # 발급 throttle(EGW00133)·200+비JSON 응답 등 — body 를 남겨 원인 추적.
        state.token_issue_failed_at = time.time()
        logger.warning("KIS 토큰 발급 실패 status=%s body=%s", res.status_code, res.text[:200])
        return
    try:
        expires_in = float(data.get("expires_in") or 86400)
    except (TypeError, ValueError):
        expires_in = 86400.0  # 비숫자 expires_in — 발급은 성공했으므로 표준 24h 로 간주
    state.token = token
    state.token_expires_at = time.time() + expires_in


def _is_fresh(expires_at: float, now: float) -> bool:
    return now < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS


async def _refresh_from_db_or_issue(client: httpx.AsyncClient, state: KisState) -> None:
    """DB 토큰 재사용, 없으면 advisory lock 하에 발급 + 같은 트랜잭션에서 영속화."""
    loaded = await kis_token_store.load(state.pool)
    if loaded and _is_fresh(loaded[1], time.time()):
        state.token, state.token_expires_at = loaded
        return
    async with kis_token_store.issue_lock(state.pool) as conn:
        # double-check — 락 대기 중 타 프로세스가 발급/저장했을 수 있다.
        loaded = await kis_token_store.load_in(conn)
        if loaded and _is_fresh(loaded[1], time.time()):
            state.token, state.token_expires_at = loaded
            return
        await _issue_token(client, state)
        if state.token:
            await kis_token_store.save_in(conn, state.token, state.token_expires_at)


async def get_access_token(
    client: httpx.AsyncClient, state: KisState | None = None
) -> str | None:
    """캐시된 토큰 반환(메모리 → DB 순), 만료 임박 시 재발급. 미설정/발급 실패 시 None."""
    state = state if state is not None else _state
    if not is_kis_configured(state):
        return None
    async with state.lock:
        now = time.time()
        if state.token and _is_fresh(state.token_expires_at, now):
            return state.token
        if state.token and now >= state.token_expires_at:
            state.token = None  # 완전 만료 — 발급 실패 시 재사용 금지
        try:
            if state.pool is None:
                await _issue_token(client, state)
            else:
                await _refresh_from_db_or_issue(client, state)
        except Exception:
            logger.warning("KIS 토큰 발급 예외", exc_info=True)
        return state.token


async def kis_get(
    client: httpx.AsyncClient,
    path: str,
    *,
    tr_id: str,
    params: dict,
    state: KisState | None = None,
    timeout: float = HTTP_TIMEOUT_SECONDS,
    extra_headers: dict | None = None,
    throttle_budget: float | None = None,
) -> dict | None:
    """KIS GET 호출. 성공(HTTP 200 & rt_cd=="0") 시 응답 body dict, 그 외 None.

    실패는 None 으로 수렴시켜 호출측(공급자 체인)이 다음 공급자로 fallback 하게 한다.
    `throttle_budget`: 레이트리밋 슬롯 대기 상한(초). None=무제한(배치), 시세 경로는
    짧게 줘 슬롯 부족 시 빠르게 다음 공급자로 넘어간다. EGW00201 수신 시 1회 재시도
    (budget 경로는 재시도 없이 즉시 포기).
    """
    state = state if state is not None else _state
    token = await get_access_token(client, state)
    if token is None:
        return None
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": state.app_key,
        "appsecret": state.app_secret,
        "tr_id": tr_id,
        "custtype": "P",  # 개인
    }
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(2):
        if not await _acquire_rate_slot(state, throttle_budget):
            return None  # 슬롯 부족 — 시세 경로는 다음 공급자로
        try:
            res = await client.get(
                state.base_url + path, headers=headers, params=params, timeout=timeout
            )
        except Exception:
            logger.warning("KIS 요청 실패 tr_id=%s path=%s", tr_id, path, exc_info=True)
            return None
        data = _safe_json(res)
        if res.status_code == 200 and data.get("rt_cd") == "0":
            return data
        # 초당 건수 초과(EGW00201, HTTP 500) — 서버 측 윈도우와의 jitter 일 수 있어 1회 재시도.
        if data.get("msg_cd") == "EGW00201" and attempt == 0 and throttle_budget is None:
            await asyncio.sleep(_RATE_RETRY_SLEEP_SECONDS)
            continue
        logger.warning(
            "KIS 오류 응답 tr_id=%s status=%s msg_cd=%s msg=%s",
            tr_id,
            res.status_code,
            data.get("msg_cd"),
            data.get("msg1") or res.text[:200],
        )
        return None
    return None
