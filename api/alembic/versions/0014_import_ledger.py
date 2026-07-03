"""import_ledger — 거래내역서 원장 (import_batches / import_ledger_entries) + trades provenance

Revision ID: 0014_import_ledger
Revises: 0013_accounts_account_number
Create Date: 2026-07-02

거래내역서 캡처를 trades(가변·파생)에서 분리해 불변 원장 레이어를 신설한다(decisions.md 2026-07-02).

- import_batches (파일 1건=1행): 원본 파일 메타 — R2 storage_key + content_sha256(재업로드 dedup)
  + parser_version(재파싱 판단) + account_hint. 파일 삭제는 R2 lifecycle 소유(만료 컬럼·정리 잡 없음).
  account_id·committed_at: 등록(commit) 시점에 채우는 생애주기 마커 — 미리보기만 한 배치(committed_at
  NULL)와 실제 등록한 배치를 구분한다(캡처는 여전히 독립적, NULL 로 시작).
- import_ledger_entries (행 1건, **append-only**): raw jsonb(행 원문 전체) + 식별/물질화 필드
  + provenance(batch_id, source_row_no). **원장은 거래 dedup 을 하지 않는다** — 모든 행을 그대로
  적재(무손실). 파일 통째 재업로드만 content_sha256 로 skip. 같은 거래의 중복 제거는 물질화(Stage 2)
  의 trade-signature dedup/merge 가 담당(계좌 단위). 거래 행은 trade_type IS NOT NULL 로 식별.
- trades.source_ledger_entry_id: 어느 원장 행에서 물질화됐는지 provenance 링크.

설계 주의(0003/0010/0012 관습 따름):
- RLS 미사용(2026-06-18 전역 제거). 사용자 격리는 앱 레이어 WHERE — ENABLE/FORCE 금지.
- 소유자는 일상 마이그레이션 실행 role 인 invest_note_app 로 통일.
- 신규 테이블 생성 + 컬럼 추가뿐이라 superuser 권한 불요 — 일상 경로(make migrate, invest_note_app)로 적용.
- FK 순서: import_ledger_entries 가 trades 컬럼 FK 대상이므로 두 테이블 먼저 생성 후 컬럼 추가.

⚠️ 작성만 — alembic upgrade 적용은 사용자/리더 confirm 후에만(운영 DB 변경). 로컬/일회용 테스트 DB 적용·검증만.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_import_ledger"
down_revision: Union[str, None] = "0013_accounts_account_number"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.import_batches (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            user_id uuid NOT NULL,
            broker_key text NOT NULL,
            parser_version text NOT NULL,
            filename text,
            content_type text,
            size_bytes bigint,
            storage_key text,
            content_sha256 text NOT NULL,
            account_hint text,
            account_id uuid,
            committed_at timestamp with time zone,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            parsed_at timestamp with time zone,
            CONSTRAINT import_batches_pkey PRIMARY KEY (id),
            CONSTRAINT import_batches_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
            CONSTRAINT import_batches_account_id_fkey
                FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE SET NULL
        );
        ALTER TABLE public.import_batches OWNER TO invest_note_app;
        CREATE INDEX import_batches_user_created_idx
            ON public.import_batches USING btree (user_id, created_at DESC);
        CREATE UNIQUE INDEX import_batches_user_sha256_key
            ON public.import_batches USING btree (user_id, content_sha256);

        CREATE TABLE public.import_ledger_entries (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            batch_id uuid NOT NULL,
            user_id uuid NOT NULL,
            source_row_no integer NOT NULL,
            traded_at_raw text,
            traded_at timestamp with time zone,
            trade_type text,
            asset_name text,
            ticker_hint text,
            isin text,
            country_code text,
            quantity numeric(18,4),
            price numeric(18,4),
            commission numeric(18,2),
            tax numeric(18,2),
            exchange_rate numeric(18,6),
            raw jsonb NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT import_ledger_entries_pkey PRIMARY KEY (id),
            CONSTRAINT import_ledger_entries_batch_id_fkey
                FOREIGN KEY (batch_id) REFERENCES public.import_batches(id) ON DELETE CASCADE,
            CONSTRAINT import_ledger_entries_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        );
        ALTER TABLE public.import_ledger_entries OWNER TO invest_note_app;
        CREATE INDEX import_ledger_entries_batch_id_idx
            ON public.import_ledger_entries USING btree (batch_id);
        """
    )

    # trades provenance 링크 — 원장 행 삭제 시 링크만 끊고 trade 는 유지(SET NULL).
    op.add_column(
        "trades",
        sa.Column("source_ledger_entry_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "trades_source_ledger_entry_id_fkey",
        "trades",
        "import_ledger_entries",
        ["source_ledger_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # FK(SET NULL) 지원 인덱스 — 원장 행 삭제 시 참조 trades 를 인덱스로 찾게 해 seq scan 회피.
    op.create_index(
        "trades_source_ledger_entry_id_idx", "trades", ["source_ledger_entry_id"]
    )


def downgrade() -> None:
    op.drop_index("trades_source_ledger_entry_id_idx", table_name="trades")
    op.drop_constraint(
        "trades_source_ledger_entry_id_fkey", "trades", type_="foreignkey"
    )
    op.drop_column("trades", "source_ledger_entry_id")
    op.execute(
        """
        DROP TABLE IF EXISTS public.import_ledger_entries;
        DROP TABLE IF EXISTS public.import_batches;
        """
    )
