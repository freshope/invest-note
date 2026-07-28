"""더미 푸시 어댑터 — 테스트 주입용(전송 없이 성공 처리)."""
from __future__ import annotations

from invest_note_api.services.push.base import PushAdapter, PushResult


class DummyPushAdapter(PushAdapter):
    def send(
        self, *, token: str, title: str, body: str, data: dict[str, str]
    ) -> PushResult:
        return PushResult(success=True, provider_message_id=f"dummy-{token[:8]}")
