"""푸시 전송 서비스 — FCM HTTP v1(Android) + APNs token-based(iOS). (Phase 2, 게이트)

핵심 계약: FCM/APNs 시크릿(env)이 없으면 조용히 no-op(로그만) — PostHog no-op 계약 사상.
전송은 best-effort — 어떤 실패도 삼켜서 통지 insert/응답을 절대 깨지 않는다. producer 훅이
notifications_repo.insert 직후 send_to_user 를 호출한다(Phase 1 무영향: push_enabled=False 면
DB·네트워크 접근 전에 반환).

⚠️ 실제 전송은 시크릿 주입 + iOS aps-environment production 승격 + 실기기 검증(#21) 후 활성.
그 전까지 이 모듈은 dormant — 코드 배선만 완료된 상태다.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from invest_note_api.config import Settings, get_settings
from invest_note_api.db_ops import device_tokens_repo

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_APNS_HOST_PROD = "https://api.push.apple.com"
_APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"
_HTTP_TIMEOUT = 10.0


def build_data_payload(notification: dict) -> dict[str, str]:
    """푸시 data 페이로드(딥링크용) — FE pushNotificationActionPerformed 가 소비.

    FCM/APNs 의 data(custom) 는 문자열 값만 허용하므로 전부 str 로 직렬화한다. source 는
    항상 'notification'(푸시는 per-user 알림 행에서만 발화 — 공지 broadcast 는 별도 경로).
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
) -> None:
    """알림 1건을 사용자 기기들에 푸시(best-effort). 시크릿 없으면 no-op(로그만).

    push_enabled=False 면 토큰 조회·네트워크 이전에 즉시 반환(Phase 1 무영향). 어떤 예외도
    삼켜 호출부(producer)를 깨지 않는다 — 통지 insert·본 작업 성공이 우선이다.
    """
    settings = settings or get_settings()
    if not settings.push_enabled:
        logger.debug("push 미설정 — no-op (user_id=%s)", user_id)
        return
    try:
        tokens = await device_tokens_repo.list_tokens(conn, user_id)
        if not tokens:
            return
        title = notification.get("title") or ""
        body = notification.get("body") or ""
        data = build_data_payload(notification)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            fcm_token = None  # FCM access token은 여러 기기에 재사용(요청당 재발급 방지)
            for t in tokens:
                platform = t.get("platform")
                token = t.get("token")
                if platform == "android" and settings.fcm_enabled:
                    if fcm_token is None:
                        fcm_token = await _fcm_access_token(client, settings)
                    await _send_fcm(client, settings, fcm_token, token, title, body, data)
                elif platform == "ios" and settings.apns_enabled:
                    await _send_apns(client, settings, token, title, body, data)
    except Exception:
        logger.warning("push 전송 실패(best-effort) user_id=%s", user_id, exc_info=True)


# ─────────────────────────── FCM HTTP v1 ───────────────────────────


async def _fcm_access_token(client: httpx.AsyncClient, settings: Settings) -> str:
    """서비스계정 JSON → OAuth2 access token(JWT assertion grant). google-auth 미의존."""
    import jwt  # pyjwt[crypto] — 지연 import(dormant 경로에서만 로드)

    sa = json.loads(settings.fcm_service_account_json)
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": sa["client_email"],
            "scope": _FCM_SCOPE,
            "aud": _GOOGLE_TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        },
        sa["private_key"],
        algorithm="RS256",
    )
    resp = await client.post(
        _GOOGLE_TOKEN_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _send_fcm(
    client: httpx.AsyncClient,
    settings: Settings,
    access_token: str,
    device_token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> None:
    """FCM v1 send — project_id 는 서비스계정 JSON 에서. data-only 가 아닌 notification+data."""
    sa = json.loads(settings.fcm_service_account_json)
    url = f"https://fcm.googleapis.com/v1/projects/{sa['project_id']}/messages:send"
    payload = {
        "message": {
            "token": device_token,
            "notification": {"title": title, "body": body},
            "data": data,
        }
    }
    resp = await client.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if resp.status_code >= 400:
        logger.warning("FCM send %s: %s", resp.status_code, resp.text[:200])


# ─────────────────────────── APNs token-based ───────────────────────────


def _apns_jwt(settings: Settings) -> str:
    """APNs provider JWT(ES256, .p8) — kid=key id, iss=team id. 짧은 만료로 요청 직전 발급."""
    import jwt

    now = int(time.time())
    return jwt.encode(
        {"iss": settings.apns_team_id, "iat": now},
        settings.apns_key_p8,
        algorithm="ES256",
        headers={"kid": settings.apns_key_id},
    )


async def _send_apns(
    client: httpx.AsyncClient,
    settings: Settings,
    device_token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> None:
    """APNs send — HTTP/2 필요(h2 미설치면 httpx 가 예외 → best-effort 로 삼켜짐)."""
    host = _APNS_HOST_SANDBOX if settings.apns_use_sandbox else _APNS_HOST_PROD
    url = f"{host}/3/device/{device_token}"
    payload = {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}, **data}
    resp = await client.post(
        url,
        headers={
            "authorization": f"bearer {_apns_jwt(settings)}",
            "apns-topic": settings.apns_bundle_id,
            "apns-push-type": "alert",
        },
        json=payload,
    )
    if resp.status_code >= 400:
        logger.warning("APNs send %s: %s", resp.status_code, resp.text[:200])
