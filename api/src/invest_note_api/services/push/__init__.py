"""푸시 전송 서비스 — Firebase Admin SDK 단일 채널.

핵심 계약: 자격증명(env)이 없으면 조용히 no-op(로그만) — PostHog no-op 계약 사상.
전송은 best-effort — 어떤 실패도 삼켜서 통지 insert/응답을 절대 깨지 않는다. producer 훅이
notifications_repo.insert 직후 send_to_user 를 호출한다(push_enabled=False 면 DB·네트워크
접근 전에 반환).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from invest_note_api.config import Settings, get_settings
from invest_note_api.db_ops import device_tokens_repo
from invest_note_api.services.push.base import PushAdapter, PushResult  # noqa: F401

logger = logging.getLogger(__name__)


def build_data_payload(notification: dict) -> dict[str, str]:
    """푸시 data 페이로드(딥링크용) — FE 알림 탭 핸들러가 소비.

    FCM 의 data 는 문자열 값만 허용하므로 전부 str 로 직렬화한다. source 는 항상
    'notification'(푸시는 per-user 알림 행에서만 발화 — 공지 broadcast 는 별도 경로).
    """
    return {
        "notification_id": str(notification.get("id", "")),
        "source": "notification",
        "type": str(notification.get("type") or ""),
        "board_type": str(notification.get("board_type") or ""),
        "ref_id": str(notification.get("ref_id") or ""),
    }


async def send_to_user(
    conn: Any,
    *,
    user_id: Any,
    notification: dict,
    settings: Settings | None = None,
    adapter: PushAdapter | None = None,
) -> None:
    """알림 1건을 사용자 기기들에 푸시(best-effort). 자격증명 없으면 no-op(로그만).

    폐기된 토큰(token_invalid)은 즉시 device_tokens 에서 삭제한다 — 재시도 가능한 실패
    (네트워크·quota)와 구분해야 토큰을 잘못 지우지 않는다. 어떤 예외도 삼켜 호출부(producer)를
    깨지 않는다 — 통지 insert·본 작업 성공이 우선이다.
    """
    settings = settings or get_settings()
    if not settings.push_enabled:
        logger.debug("push 미설정 — no-op (user_id=%s)", user_id)
        return
    try:
        tokens = await device_tokens_repo.list_tokens(conn, user_id)
        if not tokens:
            return
        if adapter is None:
            # 지연 import — 자격증명이 있는 경로에서만 firebase_admin 을 로드한다.
            from invest_note_api.services.push.firebase import FirebasePushAdapter

            # 생성자가 서비스계정 private key 를 파싱(blocking) — send 와 같이 스레드로 민다.
            adapter = await asyncio.to_thread(FirebasePushAdapter, settings)

        title = notification.get("title") or ""
        body = notification.get("body") or ""
        data = build_data_payload(notification)
        for t in tokens:
            token = t.get("token")
            if not token:
                continue
            # SDK send 는 blocking — async 라우트의 이벤트루프를 막지 않게 스레드로 밀어낸다.
            result = await asyncio.to_thread(
                adapter.send, token=token, title=title, body=body, data=data
            )
            if result.token_invalid:
                await device_tokens_repo.delete_token(conn, user_id, token)
    except Exception:
        logger.warning("push 전송 실패(best-effort) user_id=%s", user_id, exc_info=True)
