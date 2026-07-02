"""accounts_account_number — accounts.account_number 계좌번호 컬럼

Revision ID: 0013_accounts_account_number
Revises: 0012_board_reads
Create Date: 2026-07-01

내역서 업로드 시 파서가 추출한 전체 계좌번호(account_hint)로 사용자 계좌를 매칭해,
계좌가 여러 개여도 올바른 계좌를 안전하게 자동선택하기 위한 컬럼. 매칭은 FE-side 이고
BE 는 passthrough(응답 노출 + Create/Update optional 수용·raw 저장)만 담당한다.

- nullable text. 유니크/인덱스 없음 — 같은 번호 재발급/재사용 엣지 + 사용자별 스코프라
  유니크 강제가 부적절. 정규화는 FE 비교 시점(저장은 파싱 원문 raw).

⚠️ 작성만 — alembic upgrade 적용은 사용자 confirm 후에만(운영 DB 변경). 로컬/일회용
테스트 DB 적용·검증만. 컬럼 추가뿐이라 superuser 권한 불필요(invest_note_app 경로로 적용).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_accounts_account_number"
down_revision: Union[str, None] = "0012_board_reads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("account_number", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "account_number")
