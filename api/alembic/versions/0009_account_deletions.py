"""account_deletions — 회원 탈퇴 감사 로그

Revision ID: 0009_account_deletions
Revises: 0008_isin_ticker_map
Create Date: 2026-06-28

회원 탈퇴는 하드 삭제(public.users 삭제 → FK cascade)라 탈퇴자가 아무 흔적도 남기지
않는다. 탈퇴율·생존기간·사유를 집계하려고 삭제 직전에 PII 없는 감사 행 1건을 남긴다.

- user_id 에 FK 를 걸지 않는다(의도) — users(id) FK 면 ON DELETE CASCADE 로 감사 행이
  함께 지워져 목적을 잃는다. UUID 는 내부 식별자라 평문 보관(프로젝트 관례).
- signup_at: public.users.created_at 스냅샷(가입→탈퇴 생존기간 산출용).
- reason: FE 고정 코드값(not_useful/not_using/privacy/other) 또는 NULL(미선택).
  자유 텍스트는 받지 않는다(PIPA 최소수집 + PII 유입 차단).
- RLS 없음(2026-06-18 전역 제거).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
신규 테이블이라 superuser 권한 불요 — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_account_deletions"
down_revision: Union[str, None] = "0008_isin_ticker_map"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.account_deletions (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            user_id uuid NOT NULL,
            signup_at timestamp with time zone,
            reason text,
            deleted_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT account_deletions_pkey PRIMARY KEY (id)
        );
        ALTER TABLE public.account_deletions OWNER TO invest_note_app;
        CREATE INDEX account_deletions_deleted_at_idx
            ON public.account_deletions USING btree (deleted_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.account_deletions;
        """
    )
