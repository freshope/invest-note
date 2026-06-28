"""asyncpg 쿼리 묶음 — import_staging(일괄등록 preview→commit staging 영속).

preview 가 만든 staging(파싱+ticker 해소+dedup 결과)을 DB 에 저장하고 commit 이 읽는다.
in-process TTLCache 대신 DB 라 워커 재시작·레플리카 분리에도 유실되지 않는다(oauth_transient
선례 준용). public 테이블(RLS 없음). 다른 db_ops 와 동일하게 호출부가 conn 을 소유한다
(put 은 acquire_for_user 의 트랜잭션 안에서 호출돼 users FK 프로비저닝을 함께 받는다).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

# preview→commit staging TTL(초). 영속이라 워커 재시작과 무관하지만, 미완료 staging 의
# 무한 누적 방지 + commit 을 합리적 시간 내로 유도하는 상한.
STAGING_TTL_SECONDS = 600


# 만료행 정리(cleanup CTE)를 INSERT 와 한 statement 로 묶어 1 round-trip. 데이터 변경 CTE 는
# 참조 여부와 무관하게 항상 실행되므로 별도 DELETE 없이 만료행이 정리된다.
_PUT_SQL = """
WITH cleanup AS (
    DELETE FROM import_staging WHERE expires_at < $5
)
INSERT INTO import_staging (id, user_id, payload, expires_at)
VALUES ($1, $2, $3::jsonb, $4)
ON CONFLICT (id) DO UPDATE SET
    payload = excluded.payload,
    expires_at = excluded.expires_at
"""

# 미만료 staging 만 조회 — 만료행은 없는 것으로 취급(commit 에서 "staging 만료" 처리).
_GET_SQL = """
SELECT user_id, payload
  FROM import_staging
 WHERE id = $1
   AND expires_at > $2
"""

_DELETE_SQL = "DELETE FROM import_staging WHERE id = $1"


def _coerce_uuid(staging_id: str) -> UUID | None:
    """staging_id(클라이언트 제공 문자열)를 UUID 로. 형식 오류면 None(→ 미존재 취급)."""
    try:
        return UUID(staging_id)
    except (ValueError, AttributeError, TypeError):
        return None


async def put_import_staging(
    conn: Any,
    staging_id: str,
    user_id: str,
    payload: dict,
    expires_at: datetime,
) -> None:
    """staging 저장(+만료행 정리). payload 는 jsonb 직렬화(값이 float/str/int 라 정밀도 함정 없음).

    users FK 충족을 위해 호출부는 acquire_for_user 의 conn(=프로비저닝 완료)을 넘겨야 한다.
    """
    await conn.execute(
        _PUT_SQL,
        UUID(staging_id),
        UUID(user_id),
        json.dumps(payload),
        expires_at,
        datetime.now(timezone.utc),
    )


async def get_import_staging(conn: Any, staging_id: str) -> dict | None:
    """staging 조회. 부재/만료/잘못된 id 면 None. 반환 dict 에 user_id(str) 포함.

    in-memory cache 가 반환하던 형식({user_id, rows, parse_errors, ...})과 동형이라
    호출부(commit)의 user 일치 검증·payload 사용을 그대로 유지한다.
    """
    sid = _coerce_uuid(staging_id)
    if sid is None:
        return None
    row = await conn.fetchrow(_GET_SQL, sid, datetime.now(timezone.utc))
    if row is None:
        return None
    payload = row["payload"]
    payload = json.loads(payload) if isinstance(payload, str) else dict(payload)
    return {"user_id": str(row["user_id"]), **payload}


async def delete_import_staging(conn: Any, staging_id: str) -> None:
    """commit 성공 후 staging 제거. 잘못된 id 면 no-op."""
    sid = _coerce_uuid(staging_id)
    if sid is None:
        return
    await conn.execute(_DELETE_SQL, sid)
