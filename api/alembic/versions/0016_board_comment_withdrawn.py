"""board_comment_withdrawn — 탈퇴 회원 댓글 표식 컬럼

Revision ID: 0016_board_comment_withdrawn
Revises: 0015_trades_ledger_uniq
Create Date: 2026-07-05

board_comments.user_id 는 users FK ON DELETE SET NULL 이라 회원 하드삭제 시 끊기고,
user_profiles 도 CASCADE 삭제돼 어드민에서 탈퇴 회원 댓글이 '회원 미상'(작성자 원래 없음)과
구분되지 않는다. board_posts.metadata 의 author_withdrawn 표식과 동일 목적이나, board_comments
는 metadata jsonb 컬럼이 없으므로 전용 boolean 컬럼을 둔다. 탈퇴 트랜잭션(me.delete_me)이
DELETE users 직전(user_id 살아있을 때) 이 값을 true 로 스탬프한다.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
컬럼 추가뿐이라 superuser 불필요(일상 경로 invest_note_app 로 적용 가능).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_board_comment_withdrawn"
down_revision: Union[str, None] = "0015_trades_ledger_uniq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "board_comments",
        sa.Column(
            "author_withdrawn",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("board_comments", "author_withdrawn")
