"""auth_token_store — refresh token + OAuth transient (Phase 2b-1)

Revision ID: 0006_auth_token_store
Revises: 0005_user_profiles
Create Date: 2026-06-19

BE 토큰 발급(OAuth 중개)에 필요한 server-only secret 두 테이블을 함께 만든다(동일 보안 등급,
동시 적용). 둘 다 RLS 없음(2026-06-18 전역 제거) — 서버만 접근하는 비밀이라 plain pool 로 다룬다.

1) auth_refresh_tokens — refresh token 해시 저장(B5: 평문 금지) + 회전 + 만료.
   - token_hash UNIQUE: 조회 키(해시 대조). 평문은 어디에도 저장하지 않는다.
   - revoked_at: 회전 시 구 토큰 무효화 마커(NULL=유효). expires_at: 만료.

2) oauth_transient — login↔callback↔token 단계 간 단명 상태(B2: 인스턴스 무관 DB 저장).
   - key PK: state token / 일회용 authorization code 등 불투명 키.
   - kind: 'state'(state+PKCE challenge, login→callback) | 'code'(일회용 code, callback→token).
   - payload jsonb: kind 별 가변 페이로드(state 검증값·PKCE code_challenge·발급된 토큰 등).
     ⚠️ jsonb 라 B12(PKCE) 결정과 무관하게 스키마 불변(challenge 는 jsonb 키 추가일 뿐).
   - consumed_at: single-use 마커(B3: 소비 시 set, 재사용 거부). expires_at: TTL.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 0004+0005+0006 한 배치.
이 리비전은 superuser 권한이 필요 없다(테이블 생성뿐) — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_auth_token_store"
down_revision: Union[str, None] = "0005_user_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.auth_refresh_tokens (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            user_id uuid NOT NULL,
            token_hash text NOT NULL,
            issued_at timestamp with time zone DEFAULT now() NOT NULL,
            expires_at timestamp with time zone NOT NULL,
            revoked_at timestamp with time zone,
            CONSTRAINT auth_refresh_tokens_pkey PRIMARY KEY (id),
            CONSTRAINT auth_refresh_tokens_token_hash_key UNIQUE (token_hash),
            CONSTRAINT auth_refresh_tokens_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.auth_refresh_tokens OWNER TO invest_note_app;
        CREATE INDEX auth_refresh_tokens_user_id_idx
            ON public.auth_refresh_tokens USING btree (user_id);

        CREATE TABLE public.oauth_transient (
            key text NOT NULL,
            kind text NOT NULL,
            payload jsonb NOT NULL,
            expires_at timestamp with time zone NOT NULL,
            consumed_at timestamp with time zone,
            CONSTRAINT oauth_transient_pkey PRIMARY KEY (key)
        );
        ALTER TABLE public.oauth_transient OWNER TO invest_note_app;
        CREATE INDEX oauth_transient_expires_at_idx
            ON public.oauth_transient USING btree (expires_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.oauth_transient;
        DROP TABLE IF EXISTS public.auth_refresh_tokens;
        """
    )
