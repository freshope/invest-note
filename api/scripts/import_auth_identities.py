"""Supabase auth.identities export → auth_identities 적재 CLI (Phase 2a).

본체는 invest_note_api.services.auth_identity_import 에 있다(테스트와 공유).

⚠️ 운영 DB 적재는 사용자 confirm 후에만 실행한다. 기본은 --dry-run(검증만, commit 안 함).
선행 조건: 운영자가 Supabase auth.identities 를 export(CSV/JSON: provider, provider_id/sub,
user_id) + 0004_auth_identities 마이그레이션 적용.

사용법:
    cd api
    # 검증만(안전) — 카운트/유니크/anti-orphaning 가드 확인
    poetry run python scripts/import_auth_identities.py path/to/export.csv --dry-run
    # 실제 적재(사용자 confirm 후)
    poetry run python scripts/import_auth_identities.py path/to/export.csv --commit
"""

import argparse
import asyncio
import sys
from pathlib import Path

# pyproject.toml 이 package-mode=false 라 invest_note_api 가 site-packages 에 없다.
_API_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

import asyncpg  # noqa: E402

from invest_note_api.config import get_settings  # noqa: E402
from invest_note_api.services.auth_identity_import import (  # noqa: E402
    ImportValidationError,
    parse_export,
    run_import,
)


async def _main(export_path: str, *, dry_run: bool) -> int:
    rows, raw_count = parse_export(export_path)
    print(f"export 파싱: {len(rows)}행 (원시 {raw_count}레코드)")

    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL 미설정 — 적재 불가", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        async with conn.transaction():
            summary = await run_import(conn, rows, raw_count, dry_run=dry_run)
            if dry_run:
                # 검증만 통과시키고 트랜잭션을 의도적으로 롤백(commit 안 함).
                raise _DryRunRollback(summary)
    except _DryRunRollback as ok:
        print(f"[dry-run] 검증 통과(적재 안 함): {ok.summary}")
        return 0
    except ImportValidationError as e:
        print(f"[abort] rollback guard 위반 → 롤백: {e}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    print(f"[commit] 적재 완료: {summary}")
    return 0


class _DryRunRollback(Exception):
    def __init__(self, summary: dict) -> None:
        self.summary = summary


def main() -> None:
    parser = argparse.ArgumentParser(description="auth.identities export 적재")
    parser.add_argument("export_path", help="export 파일(CSV/JSON)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="검증만(기본)")
    group.add_argument("--commit", action="store_true", help="실제 적재(confirm 후)")
    args = parser.parse_args()

    # 기본은 dry-run — --commit 명시해야만 실제 적재.
    dry_run = not args.commit
    code = asyncio.run(_main(args.export_path, dry_run=dry_run))
    sys.exit(code)


if __name__ == "__main__":
    main()
