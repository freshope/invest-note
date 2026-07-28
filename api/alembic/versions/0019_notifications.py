"""notifications — per-user 알림 이력 테이블 (게시판 답변·상태변경 통지)

Revision ID: 0019_notifications
Revises: 0018_drop_import_staging
Create Date: 2026-07-22

게시판 처리 결과(관리자 답변·status 변경)를 per-user 알림 행으로 적재해 "무엇을 언제
통지받았는지" 이력을 남긴다. 공지(broadcast)는 이 테이블에 넣지 않는다 — 0012 의
high-water mark 결정을 보존(신규가입자 backfill 버그 회피)하고 이력 조회 시 UNION ALL
(notifications ∪ board_posts[notice])로 합친다.

설계 주의(0012_board_reads 관습 따름):
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.
- board_type 은 딥링크용으로 행에 저장(조회 시 join 없이 project). ref_id 는 board_posts.id.
- 인덱스는 (user_id, created_at DESC) — 피드 조회가 user 스코프 + 최신순이므로.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
컨테이너 자동미적용(배포마다 수동 upgrade).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_notifications"
down_revision: Union[str, None] = "0018_drop_import_staging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.notifications (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            type text NOT NULL,
            title text NOT NULL,
            body text,
            board_type text,
            ref_type text,
            ref_id uuid,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            read_at timestamp with time zone,
            CONSTRAINT notifications_pkey PRIMARY KEY (id),
            CONSTRAINT notifications_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.notifications OWNER TO invest_note_app;

        CREATE INDEX notifications_user_created_idx
            ON public.notifications USING btree (user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    # DROP TABLE 이 PK/FK/인덱스를 함께 제거.
    op.execute("DROP TABLE IF EXISTS public.notifications;")
