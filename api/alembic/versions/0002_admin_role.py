"""admin role — 어드민 패널 cross-user 조회용 invest_note_admin (BYPASSRLS)

Revision ID: 0002_admin_role
Revises: 0001_baseline
Create Date: 2026-06-17

어드민 패널은 trades/accounts/custom_tags(FORCE ROW LEVEL SECURITY)를 cross-user 로
조회해야 한다. 앱 역할 invest_note_app 은 비-superuser owner 라 GUC 미주입 plain acquire 시
정책상 current_user_id()=NULL → 0행이다. 이를 우회할 BYPASSRLS 역할을 별도로 둔다.

⚠️ 이 역할은 FastAPI 의 admin 전용 pool(ADMIN_DATABASE_URL)에서만, require_admin allowlist
게이트 뒤에서만 접속에 쓰인다. BYPASSRLS 는 모든 사용자 행을 무필터 노출하므로
allowlist 외부로 새면 안 된다.

비밀번호는 환경마다 다르므로 마이그레이션에 두지 않는다(시크릿 비포함). 적용 후 운영자가
  ALTER ROLE invest_note_admin LOGIN PASSWORD '<secret>';
를 1회 설정하고 그 비밀번호를 ADMIN_DATABASE_URL 에 넣는다. 역할 자체는 NOLOGIN 으로
생성해(비밀번호 설정 전 접속 불가) 사고 노출을 막는다.

forward-only(baseline 동일 정책). downgrade 는 역할 drop 을 시도하되 의존 객체가 있으면
운영자가 수동 정리한다.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_admin_role"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 역할 생성(멱등) — NOLOGIN BYPASSRLS NOSUPERUSER. superuser 는 명시적으로 배제한다
    # (BYPASSRLS 만 필요하고 superuser 는 과한 권한). 비밀번호는 운영자가 별도 설정.
    bind.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'invest_note_admin') THEN
                CREATE ROLE invest_note_admin NOLOGIN BYPASSRLS NOSUPERUSER;
            ELSE
                ALTER ROLE invest_note_admin BYPASSRLS NOSUPERUSER;
            END IF;
        END
        $$;
        """
    )
    # public 스키마 + 어드민 패널이 읽는 테이블 접근 GRANT. owner(invest_note_app)가 소유한
    # 객체이므로 명시 GRANT 가 필요하다. 어드민 CRUD 범위표에 맞춰:
    #   - 읽기 전용/읽기: 전 테이블 SELECT
    #   - 쓰기 대상(stocks UPDATE, nps_unmatched INSERT/UPDATE/DELETE)만 추가 부여
    #   - kis_tokens 는 시크릿이라 GRANT 제외(어드민 라우트도 노출 안 함)
    bind.exec_driver_sql("GRANT USAGE ON SCHEMA public TO invest_note_admin;")
    bind.exec_driver_sql(
        """
        GRANT SELECT ON
            public.users, public.accounts, public.trades, public.custom_tags,
            public.stocks, public.nps_unmatched
        TO invest_note_admin;
        """
    )
    bind.exec_driver_sql("GRANT UPDATE ON public.stocks TO invest_note_admin;")
    bind.exec_driver_sql(
        "GRANT INSERT, UPDATE, DELETE ON public.nps_unmatched TO invest_note_admin;"
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        REVOKE ALL ON public.users, public.accounts, public.trades, public.custom_tags,
            public.stocks, public.nps_unmatched FROM invest_note_admin;
        """
    )
    bind.exec_driver_sql("REVOKE USAGE ON SCHEMA public FROM invest_note_admin;")
    bind.exec_driver_sql("DROP ROLE IF EXISTS invest_note_admin;")
