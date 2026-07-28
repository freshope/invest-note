"""푸시 어댑터 인터페이스.

어댑터는 단일 device token 에 한 통의 푸시를 **동기** 전송하고 `PushResult` 를 반환한다.
(SDK 가 blocking I/O 이므로 async 호출부는 `asyncio.to_thread` 로 감싼다 — __init__.py 참고.)

`token_invalid` 는 "이 토큰은 앞으로도 못 쓴다"는 신호로, 호출부가 device_tokens row 를 지운다.
"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class PushResult(BaseModel):
    """단일 푸시 전송 결과."""

    success: bool
    provider_message_id: str | None = None
    # 토큰 폐기 신호 — 호출부가 device_tokens 의 해당 row 를 삭제한다.
    token_invalid: bool = False
    error: str | None = None


class PushAdapter(Protocol):
    def send(
        self, *, token: str, title: str, body: str, data: dict[str, str]
    ) -> PushResult: ...
