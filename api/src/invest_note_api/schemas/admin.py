"""어드민 패널 CRUD 스키마 — list 엔벨로프 / stats / 쓰기 입력.

row 응답은 DB 컬럼을 snake_case 그대로 통과한다(app 의 /stocks/quote·/stocks/meta 관례, A2).
따라서 row 자체는 dict 로 두고, 여기서는 엔벨로프·통계·**쓰기 입력 화이트리스트**만 정의한다.
쓰기 스키마는 편집 가능 필드를 막는 보안 경계이므로 extra='forbid' 로 미허용 키를 거부한다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AdminListResponse(BaseModel):
    """전 테이블 공통 목록 엔벨로프. items 는 snake_case row dict, total 은 검색 적용 전체 건수."""

    items: list[dict[str, Any]]
    total: int


class AdminStats(BaseModel):
    """대시보드 카운트. 키는 snake_case 유지(FE 가 그대로 소비).

    *_today 는 KST 당일 등록분. dau/wau/mau 는 user_profiles.last_sign_in 기준 rolling
    1/7/30일 '로그인' 활성(실제 앱 사용 아님, FE 라벨에 로그인 기준 명시).
    """

    users: int
    users_today: int
    accounts: int
    accounts_today: int
    trades: int
    trades_today: int
    stocks: int
    nps_unmatched: int
    broker_statements: int
    broker_statements_today: int
    feedback: int
    feedback_today: int
    bug_reports: int
    bug_reports_today: int
    deletions: int
    deletions_today: int
    dau: int
    wau: int
    mau: int


class UserGrowthPoint(BaseModel):
    """일별 누적 가입자 수 한 점. date 는 KST(Asia/Seoul) 기준 가입일 버킷."""

    date: date
    cumulative: int
    new_users: int


class DeletionTrendPoint(BaseModel):
    """일별 탈퇴 수 한 점. date 는 KST(Asia/Seoul) 기준 탈퇴일 버킷."""

    date: date
    deletions: int


class DeletionReasonCount(BaseModel):
    """탈퇴 사유별 건수. reason 미선택은 'unspecified'."""

    reason: str
    count: int


class AccountDeletionStats(BaseModel):
    """회원 탈퇴 통계 대시보드. 키는 snake_case 유지(FE 가 그대로 소비).

    churn_rate 는 누적 이탈률 = total_deletions / (total_users + total_deletions).
    분모는 '가입한 적 있는 전체'(현재 가입자 + 탈퇴자) — 현재 users 는 탈퇴자를 이미 제외하므로.
    """

    total_users: int
    total_deletions: int
    churn_rate: float
    deletions_30d: int
    avg_lifetime_days: float | None
    trend: list[DeletionTrendPoint]
    reasons: list[DeletionReasonCount]


class ImportBatchDetail(BaseModel):
    """거래내역서 원장 배치 상세 — 배치 메타(dict) + 원장 행 전량(dict 리스트).

    row 는 snake_case passthrough 관례(A2)를 따라 dict 로 둔다. entries[*].raw 는 파싱 원문
    전체(jsonb→object). trades dedup/merge 는 물질화 단계 소유이므로 원장은 무손실 전 행.
    """

    batch: dict[str, Any]
    entries: list[dict[str, Any]]


class StockUpdate(BaseModel):
    """stocks 수정 입력 — seed 파이프라인이 덮어쓰지 않는 필드만 화이트리스트.

    제외(seed 소유/PK): country_code, ticker, asset_name 의 seed overwrite 대상 중
    marcap*, nps_*, source, naver_checked_at, name_chosung. 이들을 어드민이 고쳐도 다음 seed 에
    되돌아가므로 입력 자체를 막는다. 미허용 키는 extra='forbid' 로 422 거부.
    전 필드 Optional — 부분 수정(PATCH) 시 전달된 키만 갱신한다.
    """

    model_config = ConfigDict(extra="forbid")

    asset_name: str | None = None
    market: str | None = None
    exchange: str | None = None
    sector: str | None = None
    currency: str | None = None
    is_active: bool | None = None
    us_index: str | None = None

    # asset_name·market 은 DB NOT NULL. 부분수정에서 명시적 null 을 보내면 UPDATE ...=NULL 로
    # 제약 위반(500)이 난다. 미전달(omit)은 기본값 None 으로 validate 되지 않으니 그대로 두고,
    # 명시적 null 만 422 로 거부한다(omit=무수정 / null=거부).
    @field_validator("asset_name", "market")
    @classmethod
    def _reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("null 로 설정할 수 없습니다 (NOT NULL 컬럼)")
        return v


class NpsUnmatchedCreate(BaseModel):
    """nps_unmatched 생성 입력 — PK(nps_name, nps_as_of) + NOT NULL holding_level 필수."""

    model_config = ConfigDict(extra="forbid")

    nps_name: str
    nps_as_of: date
    holding_level: str
    resolved_ticker: str | None = None


class NpsUnmatchedUpdate(BaseModel):
    """nps_unmatched 수정 입력 — resolved_ticker 가 핵심 편집 필드(reconcile 큐 해소).

    PK(nps_name, nps_as_of) 는 식별자라 수정 불가(경로/쿼리로만 식별). 전 필드 Optional.
    """

    model_config = ConfigDict(extra="forbid")

    holding_level: str | None = None
    resolved_ticker: str | None = None

    # holding_level 은 DB NOT NULL — 명시적 null 만 422 로 거부(omit=무수정).
    @field_validator("holding_level")
    @classmethod
    def _reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("null 로 설정할 수 없습니다 (NOT NULL 컬럼)")
        return v
