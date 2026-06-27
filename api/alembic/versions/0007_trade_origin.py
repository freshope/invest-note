"""trade_origin — trades.origin 출처 컬럼

Revision ID: 0007_trade_origin
Revises: 0006_auth_token_store
Create Date: 2026-06-27

일괄등록(거래내역서)으로 들어온 거래와 개별등록 거래를 데이터·UI상 구분하기 위한 출처 컬럼.
값: 'MANUAL'(기본=개별등록) / 'IMPORT'(거래내역서 일괄등록). INSERT 시에만 설정(불변).
server_default 'MANUAL' 이라 기존 행은 전부 MANUAL 로 채워진다(과거 import 57건은 backfill 불가 — 전방향만 적용).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
이 리비전은 superuser 권한이 필요 없다(컬럼 추가뿐) — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_trade_origin"
down_revision: Union[str, None] = "0006_auth_token_store"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column("origin", sa.Text(), nullable=False, server_default="MANUAL"),
    )


def downgrade() -> None:
    op.drop_column("trades", "origin")
