"""Phase 2a — auth.identities 적재 rollback guard 테스트.

순수 검증(validate)은 set 연산이라 DB 없이 돈다(CI 는 PG 없음). run_import wiring 은
fake conn 으로 dry-run insert skip / 검증 전파를 확인한다.

가드 케이스(P3):
  ① 정상 적재(검증 통과)
  ② 완전성 실패(파싱 drop) → ImportValidationError
  ③ 유니크 실패(중복 (provider,provider_id)) → ImportValidationError
  ④ anti-orphaning 실패(매핑 없는 public.users) → ImportValidationError  ← load-bearing
"""

import json
from uuid import uuid4

import pytest

from invest_note_api.services.auth_identity_import import (
    IdentityRow,
    ImportValidationError,
    parse_export,
    run_import,
    validate,
)

U1 = uuid4()
U2 = uuid4()
U3 = uuid4()  # lazy provisioning — export 에만 있고 public.users 엔 아직 없음(정상 초과)


def _rows() -> list[IdentityRow]:
    # U1: Google+Apple 링크(다행). U2: Kakao 단행.
    return [
        IdentityRow("google", "google-sub-1", U1),
        IdentityRow("apple", "apple-sub-1", U1),
        IdentityRow("kakao", "1234567", U2),
    ]


def test_case1_valid_passes():
    # ① 정상: public.users {U1,U2} ⊆ 매핑 {U1,U2}. raw_count 일치, 중복 없음.
    rows = _rows()
    validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


def test_case1b_lazy_provisioning_excess_export_user_ok():
    # ①' export 에 미접속 가입자(U3) 매핑이 더 있어도 정상(동수 비교 금지, false rollback 방지).
    rows = _rows() + [IdentityRow("google", "google-sub-3", U3)]
    validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


def test_case2_completeness_failure():
    # ② 파싱 drop: rows < raw_record_count → abort.
    rows = _rows()
    with pytest.raises(ImportValidationError, match="완전성"):
        validate(rows, raw_record_count=len(rows) + 2, existing_user_ids={U1, U2})


def test_case3_unique_failure():
    # ③ (provider, provider_id) 중복 → abort(Python 직접 체크, dry-run 도 검출).
    rows = _rows() + [IdentityRow("google", "google-sub-1", U2)]  # google-sub-1 중복
    with pytest.raises(ImportValidationError, match="유니크"):
        validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2})


def test_case4_anti_orphaning_failure():
    # ④ public.users 에 매핑 없는 id(U3) → abort(load-bearing 가드, 데이터 고아화 방지).
    rows = _rows()
    with pytest.raises(ImportValidationError, match="anti-orphaning"):
        validate(rows, raw_record_count=len(rows), existing_user_ids={U1, U2, U3})


# --- parse_export ---


def test_parse_csv(tmp_path):
    p = tmp_path / "export.csv"
    p.write_text(
        "provider,provider_id,user_id\n"
        f"google,google-sub-1,{U1}\n"
        f"kakao,1234567,{U2}\n"
    )
    rows, raw_count = parse_export(p)
    assert raw_count == 2
    assert rows[0] == IdentityRow("google", "google-sub-1", U1)
    assert rows[1] == IdentityRow("kakao", "1234567", U2)


def test_f14_provider_lowercased_on_parse(tmp_path):
    # ⚠️ F14: provider 를 소문자 정규화 — 런타임 _resolve_user_id 가 소문자로 조회하므로
    # 대소문자 drift 가 매핑 miss → 전 사용자 lockout 되는 것을 적재 시점에 못박는다.
    p = tmp_path / "export.csv"
    p.write_text(
        "provider,provider_id,user_id\n"
        f"Google,google-sub-1,{U1}\n"
        f"KAKAO,1234567,{U2}\n"
    )
    rows, _ = parse_export(p)
    assert rows[0].provider == "google"
    assert rows[1].provider == "kakao"


def test_parse_json_identity_data_sub_fallback(tmp_path):
    # provider_id 컬럼이 없고 identity_data.sub 만 있는 export 변형 대응.
    p = tmp_path / "export.json"
    p.write_text(
        json.dumps(
            [
                {"provider": "google", "identity_data": {"sub": "google-sub-1"}, "user_id": str(U1)},
            ]
        )
    )
    rows, raw_count = parse_export(p)
    assert raw_count == 1
    assert rows[0] == IdentityRow("google", "google-sub-1", U1)


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
    assert conn.executemany_called is False  # dry-run 은 INSERT 안 함
    assert summary["dry_run"] is True
    assert summary["rows"] == 3


@pytest.mark.asyncio
async def test_run_import_commit_inserts():
    conn = _FakeConn({U1, U2})
    rows = _rows()
    summary = await run_import(conn, rows, len(rows), dry_run=False)
    assert conn.executemany_called is True
    assert summary["dry_run"] is False


@pytest.mark.asyncio
async def test_run_import_validation_propagates_for_rollback():
    # 검증 실패가 run_import 밖으로 전파돼야 호출부 conn.transaction() 이 rollback 한다.
    conn = _FakeConn({U1, U2, U3})  # U3 고아 → anti-orphaning 실패
    rows = _rows()
    with pytest.raises(ImportValidationError):
        await run_import(conn, rows, len(rows), dry_run=False)
