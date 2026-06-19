"""Supabase auth.users export → user_profiles 백필 + rollback-guarded 검증 (Phase 2b-1).

기존 사용자 프로필은 현재 Supabase auth.users 에만 존재한다. 2c(Supabase 제거) 전에 1회
백필해야 영구 보존된다 — ⚠️ 비가역 마감: Apple 은 이름/email 을 첫 인증에만 제공하고 Kakao
email 도 optional 이라, 백필을 놓치면 재로그인으로 복구 불가(B6 의 데이터 출처가 사라짐).

검증(rollback guard) — auth_identity_import 와 동일 방향(P3 false rollback 회피):
  ① anti-orphaning(load-bearing): 백필 user_id ⊆ public.users.id(고아 FK 금지).
     ⚠️ 방향 — auth_identities 와 반대다. profile 은 FK→users 라 **존재하지 않는 user 로의 적재가
     금지**(고아 FK). export 가 users 의 부분집합이어야 한다(미접속 가입자 프로필은 적재 대상 아님).
  ② 완전성: 파싱 행수 = export 원시 레코드 수(silent parse drop 없음).
  ③ 유니크: user_id 중복 없음(1:1 PK).

parse / validate(순수) / run_import(db-io) 3분할 — 순수 검증은 DB 없이 돈다(CI 는 PG 없음).
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class ProfileRow:
    user_id: UUID
    email: str | None
    display_name: str | None
    avatar_url: str | None
    email_verified: bool | None
    providers: tuple[str, ...]
    last_sign_in: datetime | None


class ProfileImportValidationError(Exception):
    """rollback guard 위반 — 백필을 abort 한다."""


def _opt_str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _opt_dt(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _opt_bool(v) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "t", "1", "yes")


def _providers(rec: dict) -> tuple[str, ...]:
    # providers 는 배열(JSON) 또는 콤마 문자열(CSV)로 올 수 있다.
    raw = rec.get("providers")
    if raw is None:
        # 단일 provider 컬럼 폴백(Supabase auth.users.app_metadata.provider).
        single = _opt_str(rec.get("provider"))
        return (single,) if single else ()
    if isinstance(raw, str):
        raw = [p for p in (x.strip() for x in raw.split(",")) if p]
    return tuple(str(p).strip() for p in raw if str(p).strip())


def parse_export(path: str | Path) -> tuple[list[ProfileRow], int]:
    """auth.users export(CSV/JSON) → (rows, raw_record_count).

    기대 컬럼: user_id(또는 id), email, display_name(또는 name), avatar_url, email_verified,
    providers(배열/콤마) 또는 provider, last_sign_in(또는 last_sign_in_at).
    raw_record_count = 파일 원시 레코드 수(파싱 drop 검출, 완전성 가드 ②).
    """
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        raw = data if isinstance(data, list) else data.get("users", [])
    else:
        with path.open(newline="") as f:
            raw = list(csv.DictReader(f))

    rows: list[ProfileRow] = []
    for rec in raw:
        uid = _opt_str(rec.get("user_id")) or _opt_str(rec.get("id"))
        rows.append(
            ProfileRow(
                user_id=UUID(uid),
                email=_opt_str(rec.get("email")),
                display_name=_opt_str(rec.get("display_name")) or _opt_str(rec.get("name")),
                avatar_url=_opt_str(rec.get("avatar_url")),
                email_verified=_opt_bool(rec.get("email_verified")),
                providers=_providers(rec),
                last_sign_in=_opt_dt(
                    rec.get("last_sign_in") or rec.get("last_sign_in_at")
                ),
            )
        )
    return rows, len(raw)


def validate(
    rows: list[ProfileRow],
    raw_record_count: int,
    existing_user_ids: set[UUID],
) -> None:
    """rollback guard 3검증 — 위반 시 ProfileImportValidationError(commit 전 abort)."""
    # ② 완전성
    if len(rows) != raw_record_count:
        raise ProfileImportValidationError(
            f"완전성 실패: 파싱 {len(rows)}행 ≠ export {raw_record_count}레코드 "
            "(파싱 중 silent drop 발생)"
        )

    # ③ 유니크(user_id PK, 1:1)
    ids = {r.user_id for r in rows}
    if len(ids) != len(rows):
        raise ProfileImportValidationError(
            f"유니크 실패: user_id 중복 — {len(rows)}행 중 고유 {len(ids)}건"
        )

    # ① anti-orphaning(load-bearing): 백필 user_id ⊆ public.users.id (고아 FK 금지).
    #    auth_identities 와 반대 방향 — profile FK→users 라 존재하지 않는 user 적재 금지.
    orphaned = ids - existing_user_ids
    if orphaned:
        sample = sorted(str(u) for u in orphaned)[:5]
        raise ProfileImportValidationError(
            f"anti-orphaning 실패: public.users 에 없는 user_id {len(orphaned)}건(고아 FK 위험). "
            f"예: {sample}"
        )


async def run_import(conn, rows: list[ProfileRow], raw_record_count: int, *, dry_run: bool) -> dict:
    """단일 트랜잭션 백필 — existing_user_ids fetch → 검증 → insert(dry_run 이면 skip).

    검증을 INSERT **전에** 수행한다(고아 FK 위반 SQL 에러 대신 명시 가드로 abort). 위반 시
    ProfileImportValidationError 가 호출부 conn.transaction() 으로 전파돼 rollback.
    백필은 이미 존재하는 프로필을 덮지 않는다(ON CONFLICT DO NOTHING — 백필은 최초 1회 기준,
    2b 로그인 upsert 가 이후 갱신 담당).
    """
    existing_rows = await conn.fetch("SELECT id FROM public.users")
    existing_user_ids = {r["id"] for r in existing_rows}

    validate(rows, raw_record_count, existing_user_ids)

    if not dry_run:
        await conn.executemany(
            """
            INSERT INTO public.user_profiles
                (user_id, email, display_name, avatar_url, email_verified, providers, last_sign_in)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id) DO NOTHING
            """,
            [
                (
                    r.user_id,
                    r.email,
                    r.display_name,
                    r.avatar_url,
                    r.email_verified,
                    list(r.providers),
                    r.last_sign_in,
                )
                for r in rows
            ],
        )

    return {
        "rows": len(rows),
        "existing_users": len(existing_user_ids),
        "dry_run": dry_run,
    }
