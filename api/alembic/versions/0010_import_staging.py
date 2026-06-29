"""import_staging — 일괄등록 preview→commit 사이 staging 영속 테이블

Revision ID: 0010_import_staging
Revises: 0009_account_deletions
Create Date: 2026-06-28

일괄등록(거래내역서 import)은 preview(파싱+ticker 해소+dedup) → commit(INSERT) 2단계다.
중간 결과(staging)를 기존엔 in-process TTLCache(app.state.trade_staging)에만 뒀는데,
워커 재시작(로컬 --reload)·레플리카 분리·eviction 시 유실되어 commit 이 "staging 만료"
로 실패했다(특히 OpenFIGI 해소로 preview→commit 창이 긴 해외 거래에서 자주). auth 가
oauth_transient 로 같은 문제를 해결한 선례를 따라 staging 도 DB 로 영속한다(인스턴스 무관).

- id(uuid): preview 가 발급하는 staging_id(PK).
- payload jsonb: {rows, parse_errors, usd_skip_count, broker_key, account_hint}. 값이 전부
  float/str/int 라 jsonb 직렬화에 정밀도 함정 없음.
- expires_at: TTL(기본 600s). 조회는 미만료만, put 시 만료행 정리.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
신규 테이블이라 superuser 권한 불요 — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_import_staging"
down_revision: Union[str, None] = "0009_account_deletions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.import_staging (
            id uuid NOT NULL,
            user_id uuid NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            expires_at timestamp with time zone NOT NULL,
            CONSTRAINT import_staging_pkey PRIMARY KEY (id),
            CONSTRAINT import_staging_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.import_staging OWNER TO invest_note_app;
        CREATE INDEX import_staging_expires_at_idx
            ON public.import_staging USING btree (expires_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.import_staging;")
