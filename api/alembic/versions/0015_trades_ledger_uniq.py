"""trades 원장 provenance 부분 UNIQUE — 동시 재커밋 중복 INSERT 최후 방어

Revision ID: 0015_trades_ledger_uniq
Revises: 0014_import_ledger
Create Date: 2026-07-03

일괄등록 commit 은 그룹 advisory lock 안에서 기존 거래를 재조회해 dedup 하지만(routers/trades.py),
DB 레벨 제약이 없으면 lock 경합·핸들러 우회 등 예외 경로에서 같은 원장 행이 같은 계좌에 두 번
물질화될 여지가 남는다. 부분 UNIQUE 로 "한 계좌에 원장 행 1건 = trade 1건" 불변식을 DB 가 강제한다.

- 스코프 (account_id, source_ledger_entry_id): 같은 파일을 서로 다른 계좌에 등록하는 정상 흐름은
  허용(계좌가 다르므로 충돌 아님)하고, 같은 계좌 내 중복 물질화만 막는다.
- 부분 조건 WHERE source_ledger_entry_id IS NOT NULL: 개별등록(MANUAL)·0014 이전 기존 trades 는
  전부 NULL 이라 인덱스 대상에서 제외 → 기존 데이터와 무충돌, 생성 시 위반 없음.
- 위반 시 asyncpg.UniqueViolationError → commit 핸들러가 "중복 거래 감지" 로 전환(routers/trades.py).

설계 주의(0014 관습 따름):
- 인덱스는 소유 테이블(trades, invest_note_app owner)에 귀속 — 별도 OWNER 불요.
- 신규 인덱스뿐이라 superuser 불요 — 일상 경로(make migrate, invest_note_app)로 적용.

⚠️ 작성만 — alembic upgrade 적용은 사용자/리더 confirm 후에만(운영 DB 변경). 로컬/일회용 DB 검증만.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_trades_ledger_uniq"
down_revision: Union[str, None] = "0014_import_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "trades_account_ledger_entry_uniq",
        "trades",
        ["account_id", "source_ledger_entry_id"],
        unique=True,
        postgresql_where=sa.text("source_ledger_entry_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("trades_account_ledger_entry_uniq", table_name="trades")
