"""device_tokens — 푸시 토큰 등록 테이블 (Phase 2, 활성화 게이트)

Revision ID: 0020_device_tokens
Revises: 0019_notifications
Create Date: 2026-07-22

FCM(Android)/APNs(iOS) 푸시 전송 대상 토큰을 per-(user, token) 로 보관한다. 로그인 후 FE 가
등록(POST /v1/me/push-token), 로그아웃/탈퇴 시 정리. UNIQUE(user_id, token) 로 재등록은
last_seen_at upsert(중복 행 방지). users FK CASCADE 로 탈퇴 시 자동 정리.

⚠️ 코드/스키마만 — 실제 푸시 전송은 시크릿(FCM 서비스계정/APNs .p8) 주입 시에만 활성.
alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_device_tokens"
down_revision: Union[str, None] = "0019_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.device_tokens (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            token text NOT NULL,
            platform text NOT NULL,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            last_seen_at timestamp with time zone NOT NULL DEFAULT now(),
            CONSTRAINT device_tokens_pkey PRIMARY KEY (id),
            CONSTRAINT device_tokens_user_token_uniq UNIQUE (user_id, token),
            CONSTRAINT device_tokens_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.device_tokens OWNER TO invest_note_app;

        CREATE INDEX device_tokens_user_idx
            ON public.device_tokens USING btree (user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.device_tokens;")
