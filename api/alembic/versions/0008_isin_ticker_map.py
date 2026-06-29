"""isin_ticker_map — ISIN→ticker 해소 캐시 테이블

Revision ID: 0008_isin_ticker_map
Revises: 0007_trade_origin
Create Date: 2026-06-27

토스 해외(USD) import 시 ISIN 코드를 OpenFIGI 로 ticker 해소하고 결과를 캐시한다.
OpenFIGI 출력에 ISIN 이 없어(입력 전용) 마스터 백필이 불가하므로 import 시점 해소 + 캐시가 정합.

- `resolved`(negative cache): 미해결 ISIN 도 resolved=false 로 저장해 매 import 마다 재호출 방지.
- 해소 성공이면 ticker/exch_code/country_code/name 채움, 미해결이면 NULL.

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
신규 테이블이라 superuser 권한 불요 — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_isin_ticker_map"
down_revision: Union[str, None] = "0007_trade_origin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "isin_ticker_map",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("ticker", sa.Text(), nullable=True),
        sa.Column("exch_code", sa.Text(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="openfigi"),
        sa.Column(
            "resolved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("isin_ticker_map")
