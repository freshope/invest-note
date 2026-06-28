"""stocks_name_ko — stocks.name_ko 한글명 컬럼

Revision ID: 0011_stocks_name_ko
Revises: 0010_import_staging
Create Date: 2026-06-28

US 종목의 canonical asset_name 은 영문(nasdaqtrader Security Name)이라, 한글 표시명을 담을
별도 컬럼이 필요하다. Naver 백필(backfill_us_aliases)이 받아오는 US 한글명을 stock_aliases 와
더불어 이 컬럼에도 적재한다. 거래 조회는 (country_code, ticker) LEFT JOIN 으로 name_ko 를 읽어
표시명을 COALESCE(name_ko, asset_name) 한글 우선으로 노출한다(없으면 영문 fallback). KR 종목은
asset_name 이 이미 한글이라 채우지 않는다(NULL → fallback 으로 동일 표시).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬 적용·검증만.
이 리비전은 superuser 권한이 필요 없다(컬럼 추가뿐) — 일상 경로(invest_note_app)로 적용 가능.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_stocks_name_ko"
down_revision: Union[str, None] = "0010_import_staging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("name_ko", sa.Text(), nullable=True),
    )
    # 기존 US 한글명 일회성 backfill — naver 별칭은 이미 stock_aliases 에 적재돼 있다.
    # backfill_us_aliases 는 naver_checked_at IS NULL 인 신규 종목만 다루므로(이미 조회된 인기주/
    # SP500 은 제외), 이 복사가 없으면 정작 사용자가 보유하는 종목의 name_ko 가 영원히 NULL 로 남아
    # 표시가 영문 fallback 된다. ticker 당 naver 별칭은 1개라 min(alias) 로 결정적으로 고른다(다중 시 안전).
    op.execute(
        """
        UPDATE stocks s
           SET name_ko = sub.alias
          FROM (
                SELECT country_code, ticker, min(alias) AS alias
                  FROM stock_aliases
                 WHERE source = 'naver' AND country_code = 'US'
                 GROUP BY country_code, ticker
               ) sub
         WHERE sub.country_code = s.country_code
           AND sub.ticker = s.ticker
           AND s.country_code = 'US'
           AND s.name_ko IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("stocks", "name_ko")
