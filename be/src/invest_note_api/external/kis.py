"""KIS Open API(한국투자증권) 공통 클라이언트 — 토큰 캐시 + 요청 헬퍼.

토큰(`POST /oauth2/tokenP`, 유효 ~24h)은 in-process 캐시한다 — 단일 워커 전제
(멀티워커 전환 시 공유 저장소 필요). 발급은 1분당 1회 제한(EGW00133)이 있어
asyncio.Lock 으로 중복 발급을 차단한다.

시세성 TR(FHK*)은 실전/모의 tr_id 가 동일 — KIS_ENV 는 도메인 분기에만 쓴다.
(T↔V tr_id prefix 분기는 주문/계좌 TR 전용으로 이번 범위 밖.)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from invest_note_api.config import Settings
from invest_note_api.external.constants import (
    HTTP_TIMEOUT_SECONDS,
    KIS_MOCK_BASE_URL,
    KIS_REAL_BASE_URL,
)

logger = logging.getLogger(__name__)

KIS_TOKEN_PATH = "/oauth2/tokenP"

# 만료(expires_in, 보통 86400s) 임박 시 조기 재발급하는 여유 마진.
_TOKEN_REFRESH_MARGIN_SECONDS = 600.0


@dataclass
class KisState:
    """KIS 자격증명 + 토큰 캐시. 모듈 싱글톤(_state)은 configure_kis 로 초기화한다."""

    app_key: str = ""
    app_secret: str = ""
    base_url: str = KIS_REAL_BASE_URL
    token: str | None = None
    token_expires_at: float = 0.0  # epoch seconds
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_state = KisState()


def configure_kis(settings: Settings) -> KisState:
    """앱 lifespan/batch 진입점에서 호출 — 자격증명 설정 + 토큰 캐시 리셋."""
    global _state
    _state = KisState(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        base_url=KIS_MOCK_BASE_URL if settings.kis_env == "mock" else KIS_REAL_BASE_URL,
    )
    return _state


def is_kis_configured(state: KisState | None = None) -> bool:
    s = state if state is not None else _state
    return bool(s.app_key and s.app_secret)


async def _issue_token(client: httpx.AsyncClient, state: KisState) -> None:
    """토큰 발급 시도 — 성공 시 state 에 반영, 실패 시 로그만 남긴다(호출측이 None 처리)."""
    res = await client.post(
        state.base_url + KIS_TOKEN_PATH,
        json={
            "grant_type": "client_credentials",
            "appkey": state.app_key,
            "appsecret": state.app_secret,
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    data = res.json() if res.status_code == 200 else {}
    token = data.get("access_token")
    if not token:
        # 발급 throttle(EGW00133) 등 — body 의 에러 코드를 남겨 원인 추적.
        logger.warning("KIS 토큰 발급 실패 status=%s body=%s", res.status_code, res.text[:200])
        return
    state.token = token
    state.token_expires_at = time.time() + float(data.get("expires_in") or 86400)


async def get_access_token(
    client: httpx.AsyncClient, state: KisState | None = None
) -> str | None:
    """캐시된 토큰 반환, 만료 임박 시 재발급. 미설정/발급 실패 시 None."""
    state = state if state is not None else _state
    if not is_kis_configured(state):
        return None
    async with state.lock:
        now = time.time()
        if state.token and now < state.token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return state.token
        if state.token and now >= state.token_expires_at:
            state.token = None  # 완전 만료 — 발급 실패 시 재사용 금지
        try:
            await _issue_token(client, state)
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
) -> dict | None:
    """KIS GET 호출. 성공(HTTP 200 & rt_cd=="0") 시 응답 body dict, 그 외 None.

    실패는 None 으로 수렴시켜 호출측(공급자 체인)이 다음 공급자로 fallback 하게 한다.
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
    try:
        res = await client.get(
            state.base_url + path, headers=headers, params=params, timeout=timeout
        )
    except Exception:
        logger.warning("KIS 요청 실패 tr_id=%s path=%s", tr_id, path, exc_info=True)
        return None
    if res.status_code != 200:
        logger.warning(
            "KIS 비정상 응답 tr_id=%s status=%s body=%s", tr_id, res.status_code, res.text[:200]
        )
        return None
    data = res.json()
    if data.get("rt_cd") != "0":
        logger.warning(
            "KIS 오류 응답 tr_id=%s msg_cd=%s msg=%s",
            tr_id,
            data.get("msg_cd"),
            data.get("msg1"),
        )
        return None
    return data
