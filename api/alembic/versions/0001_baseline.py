"""baseline — 라이브 스키마 스냅샷 (pg_dump --schema-only, 036 적용 후)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-17

누적 마이그레이션 001~036 의 최종 상태를 단일 baseline 으로 둔다.
- 신규/빈 DB: 이 리비전이 baseline_schema.sql 을 1회 실행해 전체 스키마를 생성.
- 기존 DB(운영/개발): 적용하지 않고 `alembic stamp 0001_baseline` 으로 표시.

⚠️ baseline_schema.sql 은 PG 18 pg_dump 산출물이라 psql 전용 메타커맨드(\\restrict/\\unrestrict)를
포함한다 — exec_driver_sql(psycopg)은 이를 못 읽어 `syntax error at or near "\\"` 로 깨진다.
로드 시 `^\\` 줄을 제거한 뒤 실행한다(엔진 연결로 적용하므로 psql 복원 보호용인 이 줄 제거는 안전).
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql = (Path(__file__).resolve().parent.parent / "baseline_schema.sql").read_text()
    sql = "\n".join(line for line in sql.splitlines() if not line.startswith("\\"))
    bind = op.get_bind()
    bind.exec_driver_sql(sql)
    # pg_dump 는 search_path 를 '' 로 리셋한다(set_config) — 이후 alembic 의 비-qualified
    # alembic_version 접근이 깨지므로(이 트랜잭션 내내 지속) 복원한다.
    bind.exec_driver_sql("SET search_path TO public")


def downgrade() -> None:
    raise NotImplementedError("baseline 은 되돌리지 않는다 (forward-only)")
