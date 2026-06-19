"""Supabase auth.identities export → auth_identities 적재 + rollback-guarded 검증.

Phase 2a — IdP identity → 원래 user UUID 매핑 적재. 토큰-broker(2b)가 (provider, sub) 로
원래 UUID 를 조회할 수 있게 한다(데이터 고아화 방지, P2).

⚠️ 검증은 **동수(==) 비교 금지**(P3 false rollback). auth.identities 는 user 당 다행 가능
(Google+Apple 링크), public.users 는 lazy provisioning(첫 authenticated 요청 시 생성, db.py)이라
미접속 가입자는 export 에만 존재 → export user_id 수 > public.users 수가 **정상**이다. 그래서
검증 방향은 `public.users.id ⊆ export user_id`(모든 앱 데이터 보유자가 매핑을 갖는다)이며,
export 의 초과 user_id 는 무시한다.

테스트 가능성을 위해 parse / validate(순수) / run_import(db-io)로 3분할한다 — 순수 검증은
set 연산이라 DB 없이 돈다(CI 는 PG 없음).
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class IdentityRow:
    provider: str
    provider_id: str
    user_id: UUID


class ImportValidationError(Exception):
    """rollback guard 위반 — 적재를 abort 한다."""


def parse_export(path: str | Path) -> tuple[list[IdentityRow], int]:
    """export(CSV/JSON)를 파싱해 (rows, raw_record_count) 반환.

    raw_record_count = 파일의 원시 레코드 수(파싱 drop 검출용 — 완전성 가드 ②). 확장자로
    포맷 판별. CSV 헤더/JSON 키: provider, provider_id(또는 identity_data.sub), user_id.
    """
    path = Path(path)
    raw: list[dict] = []
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        raw = data if isinstance(data, list) else data.get("identities", [])
    else:
        with path.open(newline="") as f:
            raw = list(csv.DictReader(f))

    rows: list[IdentityRow] = []
    for rec in raw:
        # ⚠️ F14(HINGE): provider 를 소문자 정규화. _resolve_user_id 가 소문자 {google,kakao,apple}
        # 로 조회하므로 적재값이 대소문자 다르면 매핑 miss → callback 401 → 전 사용자 lockout(B1).
        provider = (rec.get("provider") or "").strip().lower()
        # provider_id 우선, 없으면 identity_data.sub 폴백(Supabase export 변형 대응).
        provider_id = (rec.get("provider_id") or "").strip()
        if not provider_id:
            identity_data = rec.get("identity_data")
            if isinstance(identity_data, str):
                identity_data = json.loads(identity_data) if identity_data else {}
            if isinstance(identity_data, dict):
                provider_id = str(identity_data.get("sub") or "").strip()
        user_id = (rec.get("user_id") or "").strip()
        rows.append(
            IdentityRow(
                provider=provider,
                provider_id=provider_id,
                user_id=UUID(user_id),
            )
        )
    return rows, len(raw)


def validate(
    rows: list[IdentityRow],
    raw_record_count: int,
    existing_user_ids: set[UUID],
) -> None:
    """rollback guard 3검증 — 위반 시 ImportValidationError(commit 전 abort).

    ② 완전성: 파싱된 행수 = export 원시 레코드 수(silent parse drop 없음).
    ③ 유니크: (provider, provider_id) 중복 없음 — Python 에서 직접 체크(dry-run 도 검출).
    ① anti-orphaning(핵심): public.users 의 모든 id 가 export 에 ≥1 매핑(고아화 방지).
       방향 주의 — export 초과분(미접속 가입자 user_id)은 정상이므로 무시한다.
    """
    # ② 완전성
    if len(rows) != raw_record_count:
        raise ImportValidationError(
            f"완전성 실패: 파싱 {len(rows)}행 ≠ export {raw_record_count}레코드 "
            "(파싱 중 silent drop 발생)"
        )

    # ③ 유니크
    pairs = {(r.provider, r.provider_id) for r in rows}
    if len(pairs) != len(rows):
        raise ImportValidationError(
            f"유니크 실패: (provider, provider_id) 중복 — {len(rows)}행 중 고유 {len(pairs)}쌍"
        )

    # ① anti-orphaning (load-bearing): public.users.id ⊆ export user_id
    mapped_user_ids = {r.user_id for r in rows}
    orphaned = existing_user_ids - mapped_user_ids
    if orphaned:
        sample = sorted(str(u) for u in orphaned)[:5]
        raise ImportValidationError(
            f"anti-orphaning 실패: 매핑 없는 public.users {len(orphaned)}건(데이터 고아화 위험). "
            f"예: {sample}"
        )


async def run_import(conn, rows: list[IdentityRow], raw_record_count: int, *, dry_run: bool) -> dict:
    """단일 트랜잭션 적재 — existing_user_ids fetch → insert(dry_run 이면 skip) → validate.

    검증 통과 시에만 commit. ImportValidationError 가 트랜잭션 밖으로 전파되면 호출부의
    conn.transaction() 이 rollback 한다(P3). dry_run=True 면 INSERT 를 건너뛰고 검증만 수행.
    반환: 요약 dict(검증 카운트).
    """
    existing_rows = await conn.fetch("SELECT id FROM public.users")
    existing_user_ids = {r["id"] for r in existing_rows}

    if not dry_run:
        await conn.executemany(
            """
            INSERT INTO public.auth_identities (provider, provider_id, user_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (provider, provider_id) DO NOTHING
            """,
            [(r.provider, r.provider_id, r.user_id) for r in rows],
        )

    # 검증은 항상 수행(dry_run 이어도 실패를 사전 보고). 위반 시 트랜잭션 rollback.
    validate(rows, raw_record_count, existing_user_ids)

    return {
        "rows": len(rows),
        "existing_users": len(existing_user_ids),
        "dry_run": dry_run,
    }
