"""board read state — 게시판 읽음/알림 상태 DB 이전 (user_notice_state / board_post_reads)

Revision ID: 0012_board_reads
Revises: 0011_stocks_name_ko
Create Date: 2026-06-28

게시판 읽음·알림 상태가 그동안 기기 localStorage(app/src/lib/board-seen.ts)에만 있어
기기 변경 시 유실되고, 신규 가입자에게 가입 전 옛 공지가 전부 안읽음으로 떴다. 판정을 전부
DB 로 옮겨 기기 무관하게 유지한다. 운영 미적용 상태라 backfill 불필요.

두 메커니즘을 유지한다(통합하지 않음 — 공지를 per-post 로 만들면 신규가입자 backfill 문제가
생기는데 high-water mark 가 이를 구조적으로 회피):
- user_notice_state: per-user high-water mark. row 없으면 has_unread 가 users.created_at
  (가입 시각)으로 fallback → 신규가입자 옛 공지 안 뜸.
- board_post_reads: per-(user, post). read_at(상세 열람)·popup_acked_at(바텀시트 안내 확인)
  은 독립 이벤트라 한 테이블의 두 nullable 컬럼으로 보관(별도 테이블 X, 한쪽만 upsert).

설계 주의(0003_board_tables 관습 따름):
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.
- 신규 테이블 생성뿐이라 superuser 권한 불요 — 일상 경로(make migrate, invest_note_app)로 적용.
- 인덱스는 PK 로 충분(board_post_reads 는 내 글 소수, user_notice_state 는 user 당 1행).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_board_reads"
down_revision: Union[str, None] = "0011_stocks_name_ko"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.user_notice_state (
            user_id uuid NOT NULL,
            notices_seen_at timestamp with time zone NOT NULL,
            CONSTRAINT user_notice_state_pkey PRIMARY KEY (user_id),
            CONSTRAINT user_notice_state_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.user_notice_state OWNER TO invest_note_app;

        CREATE TABLE public.board_post_reads (
            user_id uuid NOT NULL,
            post_id uuid NOT NULL,
            read_at timestamp with time zone,
            popup_acked_at timestamp with time zone,
            CONSTRAINT board_post_reads_pkey PRIMARY KEY (user_id, post_id),
            CONSTRAINT board_post_reads_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
            CONSTRAINT board_post_reads_post_id_fkey
                FOREIGN KEY (post_id) REFERENCES public.board_posts(id) ON DELETE CASCADE
        );
        ALTER TABLE public.board_post_reads OWNER TO invest_note_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.board_post_reads;
        DROP TABLE IF EXISTS public.user_notice_state;
        """
    )
