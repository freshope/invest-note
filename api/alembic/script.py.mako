"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

raw SQL 러너 — upgrade()/downgrade() 본문에 op.execute("...") 로 DDL 을 작성한다.
(이 프로젝트는 ORM/autogenerate 를 쓰지 않는다.)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "op.execute(\"\"\"-- TODO: DDL\"\"\")"}


def downgrade() -> None:
    ${downgrades if downgrades else "op.execute(\"\"\"-- TODO: revert DDL\"\"\")"}
