"""board tables — 멀티 게시판 구조 (board_posts / board_comments / board_attachments)

Revision ID: 0003_board_tables
Revises: 0002_drop_rls
Create Date: 2026-06-19

공지사항·사용자의견·오류신고·거래내역서 제공 등 여러 게시판을 개별 테이블로 쪼개지 않고
하나의 게시글 테이블(board_posts) + board_type discriminator + metadata jsonb 로 흡수한다.
board_comments(관리자 댓글 포함)·board_attachments(첨부 메타)는 post/comment 에 귀속.

설계 주의:
- RLS 미사용(2026-06-18 전역 제거). 사용자 격리는 앱 레이어 WHERE 로 단일화 — ENABLE/FORCE 금지.
- board_type 은 PG enum 이 아니라 text + CHECK. 후속 스펙마다 새 type 이 추가되므로 enum 의
  ALTER TYPE ADD VALUE owner/superuser 마찰을 피한다. 새 type 추가는 CHECK 교체로 확장한다.
- updated_at 자동 갱신은 baseline 의 공유 트리거 함수 public.set_updated_at() 재사용.
- 첨부 스토리지 백엔드(객체 스토리지 vs DB)는 후속 업로드 스펙에서 결정 — 여기선 shape 만 정의.
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.

이 리비전은 superuser 권한이 필요 없다(extension/role/함수 소유권 변경 없음, 테이블 생성뿐) —
일상 경로(make migrate, invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_board_tables"
down_revision: Union[str, None] = "0002_drop_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.board_posts (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            board_type text NOT NULL,
            user_id uuid,
            title text NOT NULL,
            body text DEFAULT '' NOT NULL,
            status text DEFAULT 'open' NOT NULL,
            is_pinned boolean DEFAULT false NOT NULL,
            metadata jsonb DEFAULT '{}' NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT board_posts_pkey PRIMARY KEY (id),
            CONSTRAINT board_posts_board_type_check
                CHECK (board_type IN ('notice', 'feedback', 'bug_report', 'broker_statement')),
            CONSTRAINT board_posts_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
        );
        ALTER TABLE public.board_posts OWNER TO invest_note_app;
        CREATE INDEX board_posts_type_created_idx
            ON public.board_posts USING btree (board_type, created_at DESC);
        CREATE INDEX board_posts_user_id_idx
            ON public.board_posts USING btree (user_id);
        CREATE TRIGGER board_posts_updated_at BEFORE UPDATE ON public.board_posts
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

        CREATE TABLE public.board_comments (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            post_id uuid NOT NULL,
            user_id uuid,
            is_admin boolean DEFAULT false NOT NULL,
            body text NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT board_comments_pkey PRIMARY KEY (id),
            CONSTRAINT board_comments_post_id_fkey
                FOREIGN KEY (post_id) REFERENCES public.board_posts(id) ON DELETE CASCADE,
            CONSTRAINT board_comments_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
        );
        ALTER TABLE public.board_comments OWNER TO invest_note_app;
        CREATE INDEX board_comments_post_id_created_idx
            ON public.board_comments USING btree (post_id, created_at);
        CREATE TRIGGER board_comments_updated_at BEFORE UPDATE ON public.board_comments
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

        CREATE TABLE public.board_attachments (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            post_id uuid,
            comment_id uuid,
            user_id uuid,
            original_name text NOT NULL,
            content_type text,
            size_bytes bigint,
            storage_key text,
            bucket text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT board_attachments_pkey PRIMARY KEY (id),
            CONSTRAINT board_attachments_target_check
                CHECK (post_id IS NOT NULL OR comment_id IS NOT NULL),
            CONSTRAINT board_attachments_post_id_fkey
                FOREIGN KEY (post_id) REFERENCES public.board_posts(id) ON DELETE CASCADE,
            CONSTRAINT board_attachments_comment_id_fkey
                FOREIGN KEY (comment_id) REFERENCES public.board_comments(id) ON DELETE CASCADE,
            CONSTRAINT board_attachments_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
        );
        ALTER TABLE public.board_attachments OWNER TO invest_note_app;
        CREATE INDEX board_attachments_post_id_idx
            ON public.board_attachments USING btree (post_id);
        CREATE INDEX board_attachments_comment_id_idx
            ON public.board_attachments USING btree (comment_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.board_attachments;
        DROP TABLE IF EXISTS public.board_comments;
        DROP TABLE IF EXISTS public.board_posts;
        """
    )
