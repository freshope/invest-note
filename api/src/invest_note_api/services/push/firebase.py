"""Firebase Admin SDK 기반 푸시 어댑터 — iOS/Android 단일 채널.

FCM HTTP v1 을 SDK 가 감싸고, iOS 는 Firebase 가 APNs 로 위임 발송한다(sandbox/production
호스트 매칭 불필요 — 앱 entitlement 의 aps-environment 를 Firebase 가 알아서 라우팅).

`firebase_admin.initialize_app` 은 프로세스당 1회만 호출 가능(중복 → ValueError)이라 guard 를 둔다.
"""
from __future__ import annotations

import json
import logging

import firebase_admin
from firebase_admin import credentials, exceptions, messaging

from invest_note_api.config import Settings, get_settings
from invest_note_api.services.push.base import PushAdapter, PushResult

logger = logging.getLogger(__name__)


def _ensure_initialized(settings: Settings) -> None:
    if not firebase_admin._apps:
        cred = credentials.Certificate(
            json.loads(settings.google_application_credentials_json)
        )
        firebase_admin.initialize_app(cred)


class FirebasePushAdapter(PushAdapter):
    """Firebase Admin SDK 어댑터.

    토큰 무효 3종은 모두 `token_invalid=True` 로 매핑한다. 특히 cutover 이전에 저장된
    iOS raw-APNs 토큰(64 hex)을 FCM 에 넘기면 `UnregisteredError` 가 아니라
    `InvalidArgumentError` 가 나므로, 이 매핑이 없으면 stale row 가 영원히 남는다.
    그 외(네트워크·quota)는 success=False 로만 두어 토큰을 보존한다.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        _ensure_initialized(settings or get_settings())

    def send(
        self, *, token: str, title: str, body: str, data: dict[str, str]
    ) -> PushResult:
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data=data,
            # iOS 는 aps.sound 미설정 시 무음 — 직접-APNs 시절 동작(sound="default") 보존.
            # (Android 알림음은 수신 단말의 알림 채널이 결정 — APNs config 영향 없음)
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
            ),
        )
        try:
            return PushResult(
                success=True, provider_message_id=str(messaging.send(message))
            )
        except (
            messaging.UnregisteredError,
            messaging.SenderIdMismatchError,
            exceptions.InvalidArgumentError,
        ) as e:
            return PushResult(success=False, token_invalid=True, error=str(e))
        except Exception as e:  # noqa: BLE001 — 네트워크·quota 는 best-effort
            logger.warning("푸시 발송 실패 token=%s...", token[:8], exc_info=True)
            return PushResult(success=False, error=str(e))
