"""실DB cross-user 격리 테스트 — RLS 제거 후 앱 레이어 user_id 필터가 유일한 격리 수단.

`INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG, plain postgresql://) 설정 시에만
실행한다. RLS 가 없으므로 repo 함수가 user_id 로 스코프하지 않으면 타 유저 데이터가 새어
이 테스트가 실패한다 — DB 백스톱을 대체하는 영구 회귀 가드다. CI(migrate-verify)에서 이 env
를 주입한다. 미설정 환경(기본 단위 테스트)에서는 skip.
"""
from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest

from invest_note_api.db_ops import accounts_repo, custom_tags_repo, trades_repo
from invest_note_api.errors import APIError

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB 격리 테스트 skip"
)


async def _seed_user(conn, *, name: str) -> tuple[str, str, str]:
    """user + account + BUY trade 1건 시드. (user_id, account_id, trade_id) 반환."""
    user_id = str(uuid4())
    await conn.execute("INSERT INTO public.users (id) VALUES ($1)", user_id)
    account_id = await conn.fetchval(
        "INSERT INTO accounts (user_id, name, broker, cash_balance)"
        " VALUES ($1, $2, 'TEST', 0) RETURNING id",
        user_id,
        name,
    )
    trade_id = await conn.fetchval(
        "INSERT INTO trades"
        " (user_id, account_id, asset_name, trade_type, price, quantity, ticker_symbol, exchange)"
        " VALUES ($1, $2, $3, 'BUY', 100, 1, 'TST', 'KRX') RETURNING id",
        user_id,
        account_id,
        name,
    )
    return user_id, str(account_id), str(trade_id)


async def test_repos_scope_to_user_after_rls_removed():
    conn = await asyncpg.connect(TEST_DB_URL)
    try:
        ua, aa, ta = await _seed_user(conn, name="userA")
        ub, ab, tb = await _seed_user(conn, name="userB")

        # list_accounts: A 는 A 계좌만 본다 (B 계좌 누출 금지).
        a_accounts = await accounts_repo.list_accounts(conn, ua)
        a_ids = {x["id"] for x in a_accounts}
        assert aa in a_ids
        assert ab not in a_ids

        # assert_account_exists: 본인 계좌는 통과, 타인 계좌는 400.
        await trades_repo.assert_account_exists(conn, aa, ua)
        with pytest.raises(APIError):
            await trades_repo.assert_account_exists(conn, ab, ua)

        # get_trade_by_id: 본인 거래만, 타인 거래는 None.
        assert await trades_repo.get_trade_by_id(conn, ta, ua) is not None
        assert await trades_repo.get_trade_by_id(conn, tb, ua) is None

        # patch_account: 타인 계좌 수정 불가(None), 본인 계좌는 갱신.
        assert await accounts_repo.patch_account(conn, ab, ua, {"name": "hacked"}) is None
        patched = await accounts_repo.patch_account(conn, aa, ua, {"name": "renamed"})
        assert patched is not None and patched["name"] == "renamed"

        # custom_tags: list 는 본인 것만, delete 는 타인 태그 불가(False)·본인 태그 가능(True).
        tag_a = await custom_tags_repo.create_custom_tag(conn, ua, "tagA")
        tag_b = await custom_tags_repo.create_custom_tag(conn, ub, "tagB")
        a_tag_labels = {t["label"] for t in await custom_tags_repo.list_custom_tags(conn, ua)}
        assert a_tag_labels == {"tagA"}
        assert await custom_tags_repo.delete_custom_tag(conn, ua, tag_b["id"]) is False
        assert await custom_tags_repo.delete_custom_tag(conn, ua, tag_a["id"]) is True
    finally:
        # 시드 정리 (users CASCADE 로 accounts/trades 동반 삭제).
        await conn.execute(
            "DELETE FROM public.users WHERE id = ANY($1::uuid[])",
            [ua, ub],
        )
        await conn.close()
