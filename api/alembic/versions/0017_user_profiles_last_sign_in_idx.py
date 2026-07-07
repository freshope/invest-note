"""user_profiles.last_sign_in 인덱스 — 대시보드 DAU/WAU/MAU 롤링윈도 스캔용

Revision ID: 0017_user_profiles_last_sign_in_idx
Revises: 0016_board_comment_withdrawn
Create Date: 2026-07-07

어드민 대시보드 get_stats 가 dau/wau/mau 를 각각 `last_sign_in >= now() - interval N`
으로 집계한다. user_profiles 에 last_sign_in 인덱스가 없어 로드마다 3회 seq scan 이 발생하므로
롤링윈도 범위 스캔을 받쳐줄 btree 인덱스를 둔다. NULL(미로그인) 행은 조건에서 제외되므로
인덱스 대상에서 빼 크기를 줄인다(partial).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
인덱스 추가뿐이라 superuser 불필요(일상 경로 invest_note_app 로 적용 가능).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_user_profiles_last_sign_in_idx"
down_revision: Union[str, None] = "0016_board_comment_withdrawn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "user_profiles_last_sign_in_idx",
        "user_profiles",
        ["last_sign_in"],
        postgresql_where=sa.text("last_sign_in IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("user_profiles_last_sign_in_idx", table_name="user_profiles")
