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
    # 하위호환 유지 필드. 토스 USD 임포트 도입 후 임포트된 USD 거래는 더 이상 skip 이 아니다
    # (country_code=US 로 staging). 토스 USD 경로의 비거래 행(환전·이체)은 데이터 행 매칭에서
    # 무카운트로 스킵되어 이 값은 보통 0 (다른 파서가 USD 행을 skip 할 때를 위한 호환 카운터).
    usd_skip_count: int
    # staged 된 해외(country_code != KR) 거래 수. resolved 행만 집계 → ISIN 미해결 USD 종목 제외.
    foreign_count: int = 0
    unresolved_ticker_count: int
    errors: list[ImportError]
    # 선택한 계좌 기준 정합성 검증 결과 (oversell/보유 부족 등).
    # 항목이 있는 종목 그룹은 commit 시 BE 가 그룹 단위로 skip 한다. 사용자가 인지할 수 있도록 FE 가 노출.
    # account_id 미지정 preview 호출 시 빈 리스트.
    validation_errors: list[ImportError] = []
    # validation_errors 로 제외 예정인 그룹들의 row 합계. FE 의 "신규 등록" 카운트 보정용.
    excluded_count: int = 0
    # 계좌에 이미 동일하게 존재해 변경 없이 넘어가는 행 수(noop). FE "이미 등록됨" 표시용 —
    # 재업로드 시 이미 있던 거래가 어느 카운트에도 안 잡혀 사라진 것처럼 보이는 혼란 방지.
    unchanged_count: int = 0


class ImportCommitRequest(BaseModel):
    staging_id: str
    account_id: str


class ImportCommitResponse(BaseModel):
    inserted_count: int
    merged_count: int = 0
    skipped_count: int
    error_count: int
    errors: list[ImportError]
