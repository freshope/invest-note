"""push 단위 테스트 — no-op 게이트 + payload 조립 + 폐기 토큰 정리.

실전송(Firebase Admin)은 자격증명·실기기 게이트라 여기서는 어댑터를 주입해 검증한다.
"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from invest_note_api.config import Settings
from invest_note_api.services import push
from invest_note_api.services.push.base import PushResult
from invest_note_api.services.push.dummy import DummyPushAdapter

_CRED = '{"project_id":"x"}'


def _run(coro):
    return asyncio.run(coro)


class _TrackingConn:
    """list_tokens(fetch) 가 호출되는지 추적 — no-op 게이트가 DB 를 안 건드리는지 검증."""

    def __init__(self) -> None:
        self.fetch_called = False

    async def fetch(self, query, *args):
        self.fetch_called = True
        return []


class _TokenConn:
    """토큰 목록을 돌려주고 delete 대상 토큰을 기록하는 가짜 conn."""

    def __init__(self, tokens: list[dict]) -> None:
        self._tokens = tokens
        self.deleted: list[str] = []

    async def fetch(self, query, *args):
        return self._tokens

    async def execute(self, query, *args):
        assert "delete from device_tokens" in query
        self.deleted.append(args[1])


class _RecordingAdapter:
    """send 인자를 기록하고 지정한 결과를 반환."""

    def __init__(self, result: PushResult) -> None:
        self._result = result
        self.calls: list[dict] = []

    def send(self, *, token: str, title: str, body: str, data: dict[str, str]):
        self.calls.append({"token": token, "title": title, "body": body, "data": data})
        return self._result


def test_build_data_payload_all_strings():
    notif = {
        "id": uuid4(),
        "type": "board_reply",
        "board_type": "broker_statement",
        "ref_id": uuid4(),
    }
    data = push.build_data_payload(notif)
    assert all(isinstance(v, str) for v in data.values())
    assert data["source"] == "notification"
    assert data["type"] == "board_reply"
    assert data["board_type"] == "broker_statement"


def test_build_data_payload_null_fields_empty_string():
    """board_type/ref_id 가 None(예: feedback status)이어도 빈 문자열로 안전 직렬화."""
    data = push.build_data_payload(
        {"id": uuid4(), "type": "board_status", "board_type": None, "ref_id": None}
    )
    assert data["board_type"] == ""
    assert data["ref_id"] == ""


def test_credentials_one_line_json_passthrough():
    """env 값은 변환 없이 그대로 쓰인다 — 한 줄 JSON 이 그대로 파싱돼야 한다.

    private_key 의 개행은 JSON 상 `\\n` 이스케이프라 값 전체가 한 줄로 표현된다(.env 파서가
    여러 줄 값을 못 읽는 문제를 인코딩 없이 우회). json.loads 가 실제 PEM 개행으로 복원한다.
    """
    raw = '{"project_id":"y","private_key":"-----BEGIN PRIVATE KEY-----\\nAAAA\\n-----END PRIVATE KEY-----\\n"}'
    assert "\n" not in raw  # 한 줄
    s = Settings(google_application_credentials_json=raw)
    assert s.push_enabled is True
    d = json.loads(s.google_application_credentials_json)
    assert d["project_id"] == "y"
    assert d["private_key"].startswith("-----BEGIN PRIVATE KEY-----\n")


def test_send_to_user_noop_when_disabled():
    """자격증명 없으면(Settings 기본) no-op — 토큰 조회(DB)조차 하지 않는다."""
    conn = _TrackingConn()
    settings = Settings()  # push_enabled=False
    assert settings.push_enabled is False
    _run(
        push.send_to_user(
            conn,
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=settings,
        )
    )
    assert conn.fetch_called is False


def test_send_to_user_swallows_errors_when_enabled():
    """활성이어도 전송 실패는 삼킨다(best-effort) — 호출부를 깨지 않는다."""

    class _RaisingConn:
        async def fetch(self, query, *args):
            raise RuntimeError("db down")

    settings = Settings(google_application_credentials_json=_CRED)
    assert settings.push_enabled is True
    # 예외 없이 반환되어야 한다.
    _run(
        push.send_to_user(
            _RaisingConn(),
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=settings,
        )
    )


def test_send_to_user_sends_to_every_token_with_payload():
    """플랫폼 구분 없이 모든 토큰에 동일 채널로 전송하고 딥링크 data 를 함께 싣는다."""
    conn = _TokenConn(
        [{"token": "a-tok", "platform": "ios"}, {"token": "b-tok", "platform": "android"}]
    )
    adapter = _RecordingAdapter(PushResult(success=True))
    nid = uuid4()
    _run(
        push.send_to_user(
            conn,
            user_id=uuid4(),
            notification={
                "id": nid,
                "title": "제목",
                "body": "본문",
                "type": "board_reply",
            },
            settings=Settings(google_application_credentials_json=_CRED),
            adapter=adapter,
        )
    )
    assert [c["token"] for c in adapter.calls] == ["a-tok", "b-tok"]
    assert adapter.calls[0]["title"] == "제목"
    assert adapter.calls[0]["data"]["notification_id"] == str(nid)
    assert conn.deleted == []


def test_send_to_user_deletes_invalid_token():
    """token_invalid 응답이면 device_tokens row 를 지운다.

    cutover 전에 저장된 iOS raw-APNs 토큰이 이 경로로 자연 정리된다.
    """
    conn = _TokenConn([{"token": "stale-apns", "platform": "ios"}])
    adapter = _RecordingAdapter(
        PushResult(success=False, token_invalid=True, error="unregistered")
    )
    _run(
        push.send_to_user(
            conn,
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=Settings(google_application_credentials_json=_CRED),
            adapter=adapter,
        )
    )
    assert conn.deleted == ["stale-apns"]


def test_send_to_user_keeps_token_on_retryable_failure():
    """네트워크·quota 실패(token_invalid=False)에는 토큰을 지우지 않는다."""
    conn = _TokenConn([{"token": "good-tok", "platform": "android"}])
    adapter = _RecordingAdapter(PushResult(success=False, error="timeout"))
    _run(
        push.send_to_user(
            conn,
            user_id=uuid4(),
            notification={"id": uuid4(), "title": "t", "body": "b"},
            settings=Settings(google_application_credentials_json=_CRED),
            adapter=adapter,
        )
    )
    assert conn.deleted == []


def test_dummy_adapter_accepts_data_kwarg():
    """DummyPushAdapter 가 PushAdapter 시그니처(data 포함)를 만족한다."""
    r = DummyPushAdapter().send(token="tok12345", title="t", body="b", data={"k": "v"})
    assert r.success is True
    assert r.token_invalid is False
