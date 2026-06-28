"""import_staging_repo 단위 테스트 — DB 영속 staging 의 직렬화/조회 정합.

이 테스트가 가드하는 회귀: 일괄등록 staging 을 in-process 메모리가 아니라 DB(jsonb)로
영속하므로, 워커 재시작·레플리카 분리에도 preview→commit 이 살아남는다. 핵심은 (1) float
금액의 json 왕복 무손실, (2) asyncpg jsonb 가 str 로 와도 dict 복원, (3) 잘못된/만료 id 는
graceful None(=commit 에서 "staging 만료"로 처리).

repo 는 conn 을 받으므로 fake conn 을 직접 넘긴다(pool 래퍼 불필요).
"""
from __future__ import annotations

import json
from uuid import uuid4

from invest_note_api.db_ops import import_staging_repo as repo


class RecordingConn:
    """execute/fetchrow 호출 (query, args) 를 기록하고, fetchrow 는 preset row 반환.

    (query, args) 기록이 필요해 fake_pool.FakeConnection 대신 별도 사용 — FakeConnection 은
    인자를 기록하지 않는다.
    """

    def __init__(self, fetchrow_result=None):
        self.calls: list[tuple[str, tuple]] = []
        self._fetchrow_result = fetchrow_result

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "OK"

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self._fetchrow_result


def _payload() -> dict:
    return {
        "rows": [
            {"ticker_symbol": "AAPL", "price": 191.23, "quantity": 3.0,
             "commission": 0.99, "exchange_rate": 1372.5, "country_code": "US"},
        ],
        "parse_errors": [],
        "usd_skip_count": 0,
        "broker_key": "toss_pdf",
        "account_hint": None,
    }


async def test_put_serializes_payload_as_json_preserving_floats():
    from datetime import datetime, timedelta, timezone

    conn = RecordingConn()
    payload = _payload()

    await repo.put_import_staging(
        conn, str(uuid4()), str(uuid4()), payload,
        datetime.now(timezone.utc) + timedelta(seconds=600),
    )

    # cleanup+insert 를 한 statement(CTE)로 묶어 1회 실행
    assert len(conn.calls) == 1
    put_query, put_args = conn.calls[0]
    assert "INSERT INTO import_staging" in put_query
    # payload 는 세 번째 인자(json 문자열) — 왕복 시 float 무손실
    round_tripped = json.loads(put_args[2])
    assert round_tripped == payload
    assert round_tripped["rows"][0]["price"] == 191.23


async def test_get_reconstructs_with_user_id_when_jsonb_is_str():
    payload = _payload()
    uid = uuid4()
    # asyncpg jsonb 가 str 로 오는 경우
    conn = RecordingConn(fetchrow_result={"user_id": uid, "payload": json.dumps(payload)})

    got = await repo.get_import_staging(conn, str(uuid4()))

    assert got is not None
    assert got["user_id"] == str(uid)
    assert got["rows"] == payload["rows"]
    assert got["broker_key"] == "toss_pdf"


async def test_get_reconstructs_when_jsonb_is_dict():
    payload = _payload()
    uid = uuid4()
    conn = RecordingConn(fetchrow_result={"user_id": uid, "payload": payload})

    got = await repo.get_import_staging(conn, str(uuid4()))

    assert got is not None
    assert got["user_id"] == str(uid)
    assert got["usd_skip_count"] == 0


async def test_get_returns_none_for_missing_or_expired_row():
    conn = RecordingConn(fetchrow_result=None)  # 미존재/만료 → fetchrow None
    assert await repo.get_import_staging(conn, str(uuid4())) is None


async def test_get_returns_none_for_malformed_id_without_db_call():
    conn = RecordingConn()
    assert await repo.get_import_staging(conn, "not-a-uuid") is None
    assert conn.calls == []  # 잘못된 id 는 DB 조회조차 하지 않음


async def test_delete_executes_for_valid_id_and_noops_for_malformed():
    conn = RecordingConn()

    await repo.delete_import_staging(conn, str(uuid4()))
    assert len(conn.calls) == 1
    assert "DELETE FROM import_staging" in conn.calls[0][0]

    await repo.delete_import_staging(conn, "nope")
    assert len(conn.calls) == 1  # malformed → no-op
