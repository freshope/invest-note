"""import_staging drop — 원장(import ledger)이 대체해 dead 테이블 제거

Revision ID: 0018_drop_import_staging
Revises: 0017_user_last_sign_in_idx
Create Date: 2026-07-08

일괄등록 preview→commit staging 은 0010 에서 in-process TTLCache 유실을 막으려 DB(import_staging)
로 영속화했으나, 이후 거래내역서 원장(import_batches/import_ledger_entries, 0014·0015)이
캡처·물질화 2-스테이지를 대체하면서 staging 경로는 라우터에서 제거되어 dead 상태다
(참조 잔존은 db_ops/import_staging_repo.py 와 그 단위 테스트뿐, 함께 삭제).

0014·0015 운영 배포(2026-07-08) 이후 위험 분리해 별도 리비전으로 DROP 한다.
리비전 번호는 0016·0017 이 선점해 0018 로 상향(백로그 원 표기 0016 정정).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
운영 적용 테이블 DROP 이므로 배포 시 신중히(일상 경로 invest_note_app 로 적용 가능).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_drop_import_staging"
down_revision: Union[str, None] = "0017_user_last_sign_in_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DROP TABLE 이 PK/FK/인덱스(import_staging_expires_at_idx)를 함께 제거.
    op.execute("DROP TABLE IF EXISTS public.import_staging;")


def downgrade() -> None:
    # 0010 정의 복원.
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
