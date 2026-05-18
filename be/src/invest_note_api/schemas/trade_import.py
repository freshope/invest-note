"""Import API 요청/응답 스키마."""

from __future__ import annotations

from pydantic import BaseModel


class ImportError(BaseModel):
    row_no: int
    reason: str


class ImportPreviewResponse(BaseModel):
    staging_id: str
    broker_key: str
    broker_name: str
    account_hint: str | None = None
    new_count: int
    duplicate_count: int
    error_count: int
    usd_skip_count: int
    unresolved_ticker_count: int
    errors: list[ImportError]
    # 선택한 계좌 기준 정합성 검증 결과 (oversell/보유 부족 등).
    # 항목이 있으면 FE는 commit 진행을 막아야 한다. account_id 미지정 preview 호출 시 빈 리스트.
    validation_errors: list[ImportError] = []


class ImportCommitRequest(BaseModel):
    staging_id: str
    account_id: str


class ImportCommitResponse(BaseModel):
    inserted_count: int
    merged_count: int = 0
    skipped_count: int
    error_count: int
    errors: list[ImportError]
