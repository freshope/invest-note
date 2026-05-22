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
    # 항목이 있는 종목 그룹은 commit 시 BE 가 그룹 단위로 skip 한다. 사용자가 인지할 수 있도록 FE 가 노출.
    # account_id 미지정 preview 호출 시 빈 리스트.
    validation_errors: list[ImportError] = []
    # validation_errors 로 제외 예정인 그룹들의 row 합계. FE 의 "신규 등록" 카운트 보정용.
    excluded_count: int = 0


class ImportCommitRequest(BaseModel):
    staging_id: str
    account_id: str


class ImportCommitResponse(BaseModel):
    inserted_count: int
    merged_count: int = 0
    skipped_count: int
    error_count: int
    errors: list[ImportError]
