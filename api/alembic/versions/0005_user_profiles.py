"""user_profiles — IdP 프로필 수집 (Phase 2b-1)

Revision ID: 0005_user_profiles
Revises: 0004_auth_identities
Create Date: 2026-06-19

탈-Supabase Auth Phase 2b-1 의 프로필 수집 토대. 현재 Supabase auth.users 가 보관하던
사용자 프로필(email/이름/avatar 등)을 BE 가 직접 수집·보존한다. public.users(id+created_at)는
깨끗한 anchor 로 유지하고, mutable PII 는 이 별도 테이블로 격리한다(감사·삭제 용이).

설계 주의:
- named 컬럼만 — raw_user/app_meta_data 통째 복사 금지(PIPA, 최소수집). 필요 필드만 명시.
- 2b 로그인 시 IdP userinfo 로 upsert(COALESCE — Apple/Kakao 가 null/미제공이면 기존값 유지,
  last_sign_in 만 항상 갱신, B6). 백필(import_user_profiles.py)이 기존 사용자 프로필을 1회 적재.
- user_id PK 이자 FK→users(id) ON DELETE CASCADE — 1:1, 사용자 삭제 시 프로필도 정리.
- providers text[] — 한 사용자가 여러 IdP 로 로그인 가능(union append).
- RLS 미사용(2026-06-18 전역 제거). 사용자 격리는 앱 레이어 WHERE — ENABLE/FORCE 금지.
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경).
이 리비전은 superuser 권한이 필요 없다(테이블 생성뿐) — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_user_profiles"
down_revision: Union[str, None] = "0004_auth_identities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.user_profiles (
            user_id uuid NOT NULL,
            email text,
            display_name text,
            avatar_url text,
            email_verified boolean,
            providers text[] NOT NULL DEFAULT '{}',
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            last_sign_in timestamp with time zone,
            CONSTRAINT user_profiles_pkey PRIMARY KEY (user_id),
            CONSTRAINT user_profiles_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.user_profiles OWNER TO invest_note_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.user_profiles;
        """
    )
