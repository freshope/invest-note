"""push_sender 단위 테스트 — no-op 게이트 + payload 조립. (Phase 2)

실전송(FCM/APNs HTTP)은 시크릿·실기기 게이트(#21) — 여기서는 시크릿 없을 때 no-op(네트워크·
DB 미접근)와 data payload 문자열화만 검증한다.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from invest_note_api.config import Settings
from invest_note_api.services import push_sender


def _run(coro):
    return asyncio.run(coro)


class _TrackingConn:
    """list_tokens(fetch) 가 호출되는지 추적 — no-op 게이트가 DB 를 안 건드리는지 검증."""

    def __init__(self) -> None:
        self.fetch_called = False

    async def fetch(self, query, *args):
        self.fetch_called = True
        return []


def test_build_data_payload_all_strings():
    notif = {
        "id": uuid4(),
        "type": "board_reply",
        "board_type": "broker_statement",
        "ref_id": uuid4(),
    }
    data = push_sender.build_data_payload(notif)
    assert all(isinstance(v, str) for v in data.values())
    assert data["source"] == "notification"
    assert data["type"] == "board_reply"
    assert data["board_type"] == "broker_statement"


def test_build_data_payload_null_fields_empty_string():
    """board_type/ref_id 가 None(예: feedback status)이어도 빈 문자열로 안전 직렬화."""
    data = push_sender.build_data_payload(
        {"id": uuid4(), "type": "board_status", "board_type": None, "ref_id": None}
    )
    assert data["board_type"] == ""
    assert data["ref_id"] == ""


def test_send_to_user_noop_when_disabled():
    """시크릿 없으면(Settings 기본) no-op — 토큰 조회(DB)조차 하지 않는다."""
    conn = _TrackingConn()
    settings = Settings()  # push_enabled=False
    assert settings.push_enabled is False
    _run(
        push_sender.send_to_user(
            conn,
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=settings,
        )
    )
    assert conn.fetch_called is False


def test_send_to_user_swallows_errors_when_enabled():
    """활성이어도 전송 실패는 삼킨다(best-effort) — 호출부를 깨지 않는다.

    fcm 시크릿을 넣어 push_enabled=True 로 만들고, list_tokens 가 raise 해도 예외가
    전파되지 않아야 한다(안드로이드 토큰 1건 → FCM 경로 진입 전 list_tokens 에서 터짐).
    """

    class _RaisingConn:
        async def fetch(self, query, *args):
            raise RuntimeError("db down")

    settings = Settings(fcm_service_account_json='{"project_id":"x"}')
    assert settings.push_enabled is True
    # 예외 없이 반환되어야 한다.
    _run(
        push_sender.send_to_user(
            _RaisingConn(),
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=settings,
        )
    )
