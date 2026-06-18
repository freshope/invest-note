"""drop RLS — accounts/trades/custom_tags 의 RLS 정책·FORCE 제거 + current_user_id() drop

Revision ID: 0002_drop_rls
Revises: 0001_baseline
Create Date: 2026-06-18

사용자 격리를 DB RLS 에서 앱 레이어의 명시적 `WHERE user_id = $1` 로 단일화한다(운영/개발
복잡도 축소). accounts/trades/custom_tags 의 정책·ENABLE·FORCE 를 모두 내리고, RLS 가
읽던 `public.current_user_id()`(app.current_user_id GUC) 함수를 제거한다. 정책 없이 ENABLE
만 남아있던 kis_tokens/users(둘 다 invest_note_app owner)도 일관성 위해 DISABLE 한다.

정책 DROP·DISABLE·NO FORCE 는 테이블 owner(invest_note_app) 권한으로 충분하지만, 이 리비전은
`DROP FUNCTION public.current_user_id()` 를 포함하고 그 함수 owner 가 postgres 라 **superuser
(또는 postgres) 로 실행해야 한다**(app role 은 "must be owner of function" 으로 거부). alembic
버전 테이블도 postgres 소유라 alembic 실행 자체가 superuser 를 요구한다 — baseline 과 동일.

⚠️ prod 적용 경로: api 이미지에 alembic 미포함(Dockerfile 은 src/ 만 COPY)이라 alembic 으로
못 돌린다. baseline stamp 때처럼 `docker exec <prod_db> psql -U postgres` 로 이 upgrade SQL 을
실행하고 alembic_version 을 0002_drop_rls 로 수동 갱신한다(docs/spec 롤아웃 참조).

⚠️ 적용 전제: 앱 코드가 모든 user-scoped 쿼리에 user_id 를 명시하고, accounts INSERT 가
public.current_user_id() 대신 파라미터를 쓰며, acquire_for_user 가 GUC 를 set 하지 않아야
한다(같은 브랜치에 포함). RLS 가 켜진 채 GUC 만 사라지면 전 행이 거부된다.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_drop_rls"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS "accounts: 본인만 삭제" ON public.accounts;
        DROP POLICY IF EXISTS "accounts: 본인만 삽입" ON public.accounts;
        DROP POLICY IF EXISTS "accounts: 본인만 수정" ON public.accounts;
        DROP POLICY IF EXISTS "accounts: 본인만 조회" ON public.accounts;

        DROP POLICY IF EXISTS "custom_tags: 본인만 삭제" ON public.custom_tags;
        DROP POLICY IF EXISTS "custom_tags: 본인만 삽입" ON public.custom_tags;
        DROP POLICY IF EXISTS "custom_tags: 본인만 조회" ON public.custom_tags;

        DROP POLICY IF EXISTS "trades: 본인만 삭제" ON public.trades;
        DROP POLICY IF EXISTS "trades: 본인만 삽입" ON public.trades;
        DROP POLICY IF EXISTS "trades: 본인만 수정" ON public.trades;
        DROP POLICY IF EXISTS "trades: 본인만 조회" ON public.trades;

        ALTER TABLE public.accounts    NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.custom_tags NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.trades      NO FORCE ROW LEVEL SECURITY;

        ALTER TABLE public.accounts    DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.custom_tags DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.trades      DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.kis_tokens  DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.users       DISABLE ROW LEVEL SECURITY;

        DROP FUNCTION IF EXISTS public.current_user_id();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION public.current_user_id() RETURNS uuid
            LANGUAGE sql STABLE
            AS $$
          select nullif(current_setting('app.current_user_id', true), '')::uuid
        $$;

        ALTER TABLE public.users       ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.kis_tokens  ENABLE ROW LEVEL SECURITY;

        ALTER TABLE public.accounts    ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.custom_tags ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.trades      ENABLE ROW LEVEL SECURITY;

        ALTER TABLE public.accounts    FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.custom_tags FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.trades      FORCE ROW LEVEL SECURITY;

        CREATE POLICY "accounts: 본인만 삭제" ON public.accounts FOR DELETE USING ((public.current_user_id() = user_id));
        CREATE POLICY "accounts: 본인만 삽입" ON public.accounts FOR INSERT WITH CHECK ((public.current_user_id() = user_id));
        CREATE POLICY "accounts: 본인만 수정" ON public.accounts FOR UPDATE USING ((public.current_user_id() = user_id)) WITH CHECK ((public.current_user_id() = user_id));
        CREATE POLICY "accounts: 본인만 조회" ON public.accounts FOR SELECT USING ((public.current_user_id() = user_id));

        CREATE POLICY "custom_tags: 본인만 삭제" ON public.custom_tags FOR DELETE USING ((public.current_user_id() = user_id));
        CREATE POLICY "custom_tags: 본인만 삽입" ON public.custom_tags FOR INSERT WITH CHECK ((public.current_user_id() = user_id));
        CREATE POLICY "custom_tags: 본인만 조회" ON public.custom_tags FOR SELECT USING ((public.current_user_id() = user_id));

        CREATE POLICY "trades: 본인만 삭제" ON public.trades FOR DELETE USING ((public.current_user_id() = user_id));
        CREATE POLICY "trades: 본인만 삽입" ON public.trades FOR INSERT WITH CHECK ((public.current_user_id() = user_id));
        CREATE POLICY "trades: 본인만 수정" ON public.trades FOR UPDATE USING ((public.current_user_id() = user_id)) WITH CHECK ((public.current_user_id() = user_id));
        CREATE POLICY "trades: 본인만 조회" ON public.trades FOR SELECT USING ((public.current_user_id() = user_id));
        """
    )
