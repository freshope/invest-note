"""사용자 정의 분석 태그 레지스트리 repo — 선택 가능한 태그 카탈로그.

trades.custom_tags(거래에 선택된 라벨)와 별개로, 사용자가 만든 태그 목록을 영속한다.
연결은 acquire_for_user 로 RLS-scoped 이지만, insert/delete 는 user_id 를 명시해 방어한다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

PG_DELETE_ZERO = "DELETE 0"


def custom_tag_row_to_dict(row: Any) -> dict:
    d = dict(row)
    if isinstance(d.get("id"), UUID):
        d["id"] = str(d["id"])
    return d


async def list_custom_tags(conn: Any, user_id: str) -> list[dict]:
    """사용자 레지스트리 태그 목록(가나다순) — [{id, label}]."""
    rows = await conn.fetch(
        "SELECT id, label FROM custom_tags WHERE user_id = $1 ORDER BY label",
        user_id,
    )
    return [custom_tag_row_to_dict(r) for r in rows]


async def create_custom_tag(conn: Any, user_id: str, label: str) -> dict:
    """레지스트리에 태그 추가 — (user_id, label) 멱등. 이미 있으면 기존 행 반환."""
    row = await conn.fetchrow(
        """
        INSERT INTO custom_tags (user_id, label) VALUES ($1, $2)
        ON CONFLICT (user_id, label) DO NOTHING
        RETURNING id, label
        """,
        user_id,
        label,
    )
    if row is None:  # conflict — 기존 행 조회
        row = await conn.fetchrow(
            "SELECT id, label FROM custom_tags WHERE user_id = $1 AND label = $2",
            user_id,
            label,
        )
    return custom_tag_row_to_dict(row)


async def delete_custom_tag(conn: Any, user_id: str, tag_id: str) -> bool:
    """레지스트리에서만 제거 — 과거 거래의 custom_tags 라벨은 불변."""
    result = await conn.execute(
        "DELETE FROM custom_tags WHERE id = $1 AND user_id = $2",
        tag_id,
        user_id,
    )
    return result != PG_DELETE_ZERO
