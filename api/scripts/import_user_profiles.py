"""Supabase auth.users export → user_profiles 백필 CLI (Phase 2b-1).

본체는 invest_note_api.services.user_profile_import 에 있다(테스트와 공유).

⚠️ 운영 DB 백필은 사용자 confirm 후에만 실행한다. 기본은 --dry-run(검증만, commit 안 함).
⚠️ 비가역 마감 — 2c(Supabase 제거) 전에 1회 백필 필수(Apple/Kakao 가 재로그인 시 프로필 미제공).
선행 조건: 운영자가 Supabase auth.users export(2a auth.identities 와 같은 덤프에 프로필 컬럼
포함: user_id/id, email, display_name/name, avatar_url, email_verified, providers, last_sign_in)
+ 0005_user_profiles 마이그레이션 적용 + identity 적재(2a) 선행(FK 정합).

사용법:
    cd api
    poetry run python scripts/import_user_profiles.py path/to/users.csv --dry-run
    poetry run python scripts/import_user_profiles.py path/to/users.csv --commit
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
from invest_note_api.services.user_profile_import import (  # noqa: E402
    ProfileImportValidationError,
    parse_export,
    run_import,
)


class _DryRunRollback(Exception):
    def __init__(self, summary: dict) -> None:
        self.summary = summary


async def _main(export_path: str, *, dry_run: bool) -> int:
    rows, raw_count = parse_export(export_path)
    print(f"export 파싱: {len(rows)}행 (원시 {raw_count}레코드)")

    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL 미설정 — 백필 불가", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        async with conn.transaction():
            summary = await run_import(conn, rows, raw_count, dry_run=dry_run)
            if dry_run:
                raise _DryRunRollback(summary)
    except _DryRunRollback as ok:
        print(f"[dry-run] 검증 통과(백필 안 함): {ok.summary}")
        return 0
    except ProfileImportValidationError as e:
        print(f"[abort] rollback guard 위반 → 롤백: {e}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    print(f"[commit] 백필 완료: {summary}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="auth.users export 프로필 백필")
    parser.add_argument("export_path", help="export 파일(CSV/JSON)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="검증만(기본)")
    group.add_argument("--commit", action="store_true", help="실제 백필(confirm 후)")
    args = parser.parse_args()

    dry_run = not args.commit
    code = asyncio.run(_main(args.export_path, dry_run=dry_run))
    sys.exit(code)


if __name__ == "__main__":
    main()
