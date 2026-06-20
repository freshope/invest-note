"""Phase 2b-1 — auth.users 프로필 백필 rollback guard 테스트.

순수 검증(validate)은 set 연산이라 DB 없이 돈다(CI 는 PG 없음). run_import wiring 은 fake conn
으로 dry-run insert skip / 검증 전파를 확인한다.

가드 케이스:
  ① anti-orphaning: 백필 user_id ⊆ public.users.id (고아 FK 금지). ⚠️ auth_identities 와 반대 방향.
  ② 완전성(파싱 drop) → ProfileImportValidationError
  ③ 유니크(user_id 중복) → ProfileImportValidationError
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from invest_note_api.services.user_profile_import import (
    ProfileImportValidationError,
    ProfileRow,
    parse_export,
    run_import,
    validate,
)

U1 = uuid4()
U2 = uuid4()
U_GHOST = uuid4()  # public.users 에 없는 user_id (고아 FK 유발)


def _rows():
    return [
        ProfileRow(U1, "u1@e.com", "유저1", None, True, ("google",),
                   datetime(2026, 6, 1, tzinfo=timezone.utc)),
        ProfileRow(U2, "u2@e.com", "유저2", None, None, ("kakao",),
                   datetime(2026, 6, 2, tzinfo=timezone.utc)),
    ]


def test_case1_valid_passes():
    # 정상: 백필 {U1,U2} ⊆ public.users {U1,U2}. raw_count 일치, 중복 없음.
    rows = _rows()
    validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


def test_case1b_users_superset_ok():
    # public.users 가 백필보다 많아도 정상(미접속 가입자 등 — 백필은 부분집합이면 됨).
    rows = _rows()
    validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2, uuid4()})


def test_case2_completeness_failure():
    # 파싱 drop: rows < raw_record_count → abort.
    rows = _rows()
    with pytest.raises(ProfileImportValidationError, match="완전성"):
        validate(rows, raw_record_count=len(rows) + 1, existing_user_ids={U1, U2})


def test_case3_unique_failure():
    # user_id 중복(PK) → abort.
    rows = _rows() + [
        ProfileRow(U1, "dup@e.com", None, None, None, (), None)
    ]
    with pytest.raises(ProfileImportValidationError, match="유니크"):
        validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


def test_case4_anti_orphaning_failure():
    # 백필 user_id 가 public.users 에 없음(U_GHOST) → 고아 FK → abort(load-bearing).
    rows = _rows() + [
        ProfileRow(U_GHOST, "ghost@e.com", None, None, None, (), None)
    ]
    with pytest.raises(ProfileImportValidationError, match="anti-orphaning"):
        validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


# --- parse_export ---


def test_parse_csv():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "users.csv"
        p.write_text(
            "user_id,email,display_name,avatar_url,email_verified,providers,last_sign_in\n"
            f"{U1},u1@e.com,유저1,,true,\"google,kakao\",2026-06-01T00:00:00Z\n"
        )
        rows, raw_count = parse_export(p)
    assert raw_count == 1
    r = rows[0]
    assert r.user_id == U1
    assert r.email == "u1@e.com"
    assert r.display_name == "유저1"
    assert r.avatar_url is None
    assert r.email_verified is True
    assert r.providers == ("google", "kakao")
    assert r.last_sign_in == datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_parse_json_named_columns_only():
    # PIPA: named 컬럼만 파싱. raw_user_meta_data 같은 임의 키는 무시(통째 저장 안 함).
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "users.json"
        p.write_text(json.dumps([
            {
                "id": str(U2),
                "email": "u2@e.com",
                "name": "유저2",
                "providers": ["apple"],
                "raw_user_meta_data": {"secret": "should-not-be-stored"},
            }
        ]))
        rows, raw_count = parse_export(p)
    assert raw_count == 1
    r = rows[0]
    assert r.user_id == U2
    assert r.display_name == "유저2"  # name 폴백
    assert r.providers == ("apple",)
    # ProfileRow 에 raw_user_meta_data 를 담는 필드가 없다(named 컬럼만, PIPA).
    assert not hasattr(r, "raw_user_meta_data")


# --- run_import wiring (fake conn) ---


class _FakeConn:
    def __init__(self, existing_ids):
        self._existing = existing_ids
        self.executemany_called = False

    async def fetch(self, query):
        assert "FROM public.users" in query
        return [{"id": u} for u in self._existing]

    async def executemany(self, query, args):
        self.executemany_called = True


@pytest.mark.asyncio
async def test_run_import_dry_run_skips_insert():
    conn = _FakeConn({U1, U2})
    rows = _rows()
    summary = await run_import(conn, rows, len(rows), dry_run=True)
    assert conn.executemany_called is False
    assert summary["dry_run"] is True
    assert summary["rows"] == 2


@pytest.mark.asyncio
async def test_run_import_commit_inserts():
    conn = _FakeConn({U1, U2})
    rows = _rows()
    await run_import(conn, rows, len(rows), dry_run=False)
    assert conn.executemany_called is True


@pytest.mark.asyncio
async def test_run_import_validation_propagates_for_rollback():
    # 고아 FK(U_GHOST) → 검증 실패가 INSERT 전에 전파 → 호출부 transaction rollback.
    conn = _FakeConn({U1, U2})
    rows = _rows() + [ProfileRow(U_GHOST, None, None, None, None, (), None)]
    with pytest.raises(ProfileImportValidationError):
        await run_import(conn, rows, len(rows), dry_run=False)
    assert conn.executemany_called is False  # 검증이 INSERT 전이라 적재 안 됨
