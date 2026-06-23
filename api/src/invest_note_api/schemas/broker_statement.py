"""거래내역서 제보 입력 스키마 — app-side board write 전용(broker_statement).

보안 경계: **board_type 필드 없음**(서버 하드코딩), **user_id 없음**(토큰에서), extra='forbid'
로 미허용 키 거부. storage_key/bucket 은 presign 시 서버가 생성한 값을 그대로 되받되 라우터가
prefix·size·content_type 을 재검증한다.

⚠️ wire 포맷은 snake_case 다(다른 /v1 CamelModel 과 다름). FE 는 snake 로 보낸다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

# metadata.type — 제보 맥락 구분(미지원 증권사 / 해외 거래 포함).
StatementType = Literal["unsupported_broker", "overseas_trade"]


class PresignRequest(BaseModel):
    """presign 요청 — 업로드할 파일 메타. 서버가 storage_key 를 생성해 PUT URL 을 발급한다."""

    model_config = ConfigDict(extra="forbid")

    original_name: str
    content_type: str
    size_bytes: int


class AttachmentRef(BaseModel):
    """submit 시 되받는 첨부 참조 — presign 응답의 storage_key/bucket 을 그대로 싣는다."""

    model_config = ConfigDict(extra="forbid")

    storage_key: str
    original_name: str
    content_type: str
    size_bytes: int


class SubmitRequest(BaseModel):
    """제보 등록 요청. consent 는 True 만 허용(False 면 422). board_type 미수신."""

    model_config = ConfigDict(extra="forbid")

    type: StatementType
    broker: str
    country: str | None = None
    note: str | None = None
    consent: bool
    attachment: AttachmentRef

    @field_validator("consent")
    @classmethod
    def _require_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("수집·이용 동의가 필요합니다.")
        return v
