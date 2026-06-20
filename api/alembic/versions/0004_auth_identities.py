"""auth_identities — IdP identity → 원래 user UUID 매핑 (Phase 2a)

Revision ID: 0004_auth_identities
Revises: 0003_board_tables
Create Date: 2026-06-19

탈-Supabase Auth Phase 2(token-broker)의 토대. BE 가 IdP(Google/Kakao/Apple)와 직접
대화하면 IdP 고유 sub 를 받는데, 기존 데이터는 모두 Supabase 가 발급한 public.users.id(UUID)에
묶여 있다. (provider, provider_id) → 원래 user UUID 매핑을 보관해 BE 토큰 sub 를 원래 UUID 로
발급할 수 있게 한다(데이터 고아화 방지, P2). Supabase auth.identities export 를 여기에 적재한다.

설계 주의:
- RLS 미사용(2026-06-18 전역 제거). 사용자 격리는 앱 레이어 WHERE — ENABLE/FORCE 금지.
- provider_id 는 Supabase auth.identities.provider_id 를 그대로 담는다(provider 별 sub 의미):
  Google=OIDC sub, Kakao=Kakao 숫자 user id, Apple=Service ID 재사용으로 sub 보존.
- (provider, provider_id) UNIQUE — 2b 런타임 매칭이 이 쌍으로 조회한다.
- user_id FK ON DELETE CASCADE — 사용자 삭제 시 매핑도 정리.
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경).
이 리비전은 superuser 권한이 필요 없다(테이블 생성뿐) — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_auth_identities"
down_revision: Union[str, None] = "0003_board_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.auth_identities (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            provider text NOT NULL,
            provider_id text NOT NULL,
            user_id uuid NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT auth_identities_pkey PRIMARY KEY (id),
            CONSTRAINT auth_identities_provider_provider_id_key
                UNIQUE (provider, provider_id),
            CONSTRAINT auth_identities_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.auth_identities OWNER TO invest_note_app;
        CREATE INDEX auth_identities_user_id_idx
            ON public.auth_identities USING btree (user_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.auth_identities;
        """
    )
